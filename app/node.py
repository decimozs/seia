import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from app.state import AgentState
from app.utils import load_prompt

load_dotenv()

COLLECTION_NAME = "seia-collection"
EMBED_MODEL = "all-MiniLM-L6-v2"

embedder = SentenceTransformer(EMBED_MODEL)

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ.get("QDRANT_API_KEY"),
)

model = ChatOllama(
    model="gemini-3-flash-preview:cloud",
    base_url="https://ollama.com",
)

EXTRACTOR_SYSTEM_PROMPT = SystemMessage(
    content=load_prompt("app/prompts/extraction_agent_prompt.md")
)


def extract_node(state: AgentState) -> dict:
    raw = state.get("raw_text")
    response = model.invoke([EXTRACTOR_SYSTEM_PROMPT, HumanMessage(content=raw)])

    return {"structured_data": response.content, "status": "processed"}


AUDITOR_SYSTEM_PROMPT = SystemMessage(
    content=load_prompt("app/prompts/policy_auditor_agent_prompt.md")
)


def retrieve_policies(query: str, top_k: int = 5) -> list[str]:
    query_vec = embedder.encode(query).tolist()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        limit=top_k,
        with_payload=True,
    )
    return [hit.payload["text"] for hit in results.points]


def audit_node(state: AgentState) -> dict:
    expense = state.get("structured_data")
    retrieved_policies = retrieve_policies(str(expense))
    policy_context = "\n".join(f"- {p}" for p in retrieved_policies)

    grounded_system_prompt = SystemMessage(
        content=f"{AUDITOR_SYSTEM_PROMPT}\n\n"
        f"Relevant company policies:\n{policy_context}"
    )

    # 3. Audit with grounded context
    response = model.invoke(
        [
            grounded_system_prompt,
            HumanMessage(content=f"Review this expense: {expense}"),
        ]
    )

    raw = re.sub(r"```(?:json)?\s*|\s*```", "", response.content).strip()
    parsed = json.loads(raw)

    return {
        "status": parsed.get("status", ""),
        "audit_remarks": parsed.get("audit_remarks", ""),
        "retrieved_policies": retrieved_policies,
    }


def output_node(state: AgentState):
    data = state["structured_data"]

    if data is None:
        return state

    print(f"Output Data: {data}")
    print(f"Output State: {state}")

    return state


def human_review_node(state: AgentState) -> dict:
    print("\nPolicy violation detected. Human review required.")
    print(f"Audit Remarks: {state['audit_remarks']}")
    print(f"Expense Data:\n{state['structured_data']}\n")

    feedback = input(
        "Enter your decision (approve/reject) and remarks, e.g. 'approve: looks fine': "
    ).strip()

    if feedback.lower().startswith("approve"):
        return {
            "status": "approved",
            "human_feedback": feedback,
        }
    else:
        return {
            "status": "rejected",
            "human_feedback": feedback,
        }
