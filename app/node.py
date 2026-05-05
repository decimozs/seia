import json
import logging
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from qdrant_client import QdrantClient
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from app.state import AgentState
from app.utils import load_prompt

console = Console()

load_dotenv()

COLLECTION_NAME = "seia-collection"
EMBED_MODEL = "nomic-embed-text"

embeddings = OllamaEmbeddings(model=EMBED_MODEL)

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ.get("QDRANT_API_KEY"),
)

model = ChatOllama(model="lfm2.5-thinking", temperature=0)

EXTRACTOR_SYSTEM_PROMPT = SystemMessage(
    content=load_prompt("app/prompts/extraction_agent_prompt.md")
)


def extract_node(state: AgentState) -> dict:
    raw = state.get("raw_text")
    response = model.invoke([EXTRACTOR_SYSTEM_PROMPT, HumanMessage(content=raw)])
    content = response.content
    if isinstance(content, list):
        content = "".join(
            [i if isinstance(i, str) else i.get("text", "") for i in content]
        )

    content = content.replace("```json", "").replace("```", "").strip()

    try:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            structured_data = json.loads(match.group())
        else:
            structured_data = {"error": "No JSON found in response", "raw": content}

    except json.JSONDecodeError:
        structured_data = {"error": "Invalid JSON format", "raw": content}

    return {
        "structured_data": structured_data,
        "status": "processed",
    }


AUDITOR_SYSTEM_PROMPT = SystemMessage(
    content=load_prompt("app/prompts/policy_auditor_agent_prompt.md")
)


def retrieve_policies(query: str, top_k: int = 5) -> list[str]:
    query_vec = embeddings.embed_query(query)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
        with_payload=True,
    )
    hits = [hit.payload["text"] for hit in results.points]
    return hits


def audit_node(state: AgentState) -> dict:
    expense = state.get("structured_data")
    retrieved_policies = retrieve_policies(str(expense))
    policy_context = "\n".join(f"- {p}" for p in retrieved_policies)
    prompt_text = AUDITOR_SYSTEM_PROMPT.content
    grounded_system_prompt = SystemMessage(
        content=f"{prompt_text}\n\nRelevant company policies:\n{policy_context}"
    )
    response = model.invoke(
        [
            grounded_system_prompt,
            HumanMessage(content=f"Review this expense: {expense}"),
        ]
    )
    raw = re.sub(r"```(?:json)?\s*|\s*```", "", response.content).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"status": "error", "audit_remarks": raw}
    return {
        "status": parsed.get("status", ""),
        "audit_remarks": parsed.get("audit_remarks", ""),
        "retrieved_policies": retrieved_policies,
    }


def output_node(state: AgentState):
    return state


def human_review_node(state: AgentState) -> dict:
    logger = logging.getLogger("uvicorn.access")
    original_disabled = logger.disabled
    logger.disabled = True
    logging.disable(logging.INFO)

    try:
        with console.screen():
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Field", width=20)
            table.add_column("Value", width=40)
            for key, value in state["structured_data"].items():
                table.add_row(str(key).capitalize(), str(value))
            console.print(
                Panel(
                    f"[bold red]Violation Detected:[/bold red]\n{state['audit_remarks']}",
                    title="[bold yellow] SEIA Audit Intervention [/bold yellow]",
                    border_style="yellow",
                ),
                justify="center",
            )
            console.print(table, justify="center")
            feedback = Prompt.ask(
                "\n[bold cyan]Decision (approve/reject)[/bold cyan]"
            ).strip()

    finally:
        logger.disabled = original_disabled
        logging.disable(logging.NOTSET)
    if feedback.lower().startswith("approve"):
        return {"status": "approved", "human_feedback": feedback}
    else:
        return {"status": "rejected", "human_feedback": feedback}
