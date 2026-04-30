import os
import shutil
import tempfile

from fastapi import BackgroundTasks, FastAPI, Request
from langchain_community.document_loaders import PyPDFLoader
from pydantic import BaseModel

from app.agent import graph
from app.state import AgentState


class InvoiceRequest(BaseModel):
    raw_text: str


app = FastAPI()


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}


config = {"configurable": {"thread_id": "thread-1"}}


def run_graph(initial_state: AgentState):
    result = graph.invoke(initial_state, config=config)


@app.post("/process-invoice")
async def process_invoice(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    file = next(iter(form.values()))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        shutil.copyfileobj(file.file, temp_pdf)
        temp_path = temp_pdf.name

    try:
        loader = PyPDFLoader(temp_path)
        pages = loader.load()
        content = "\n\n".join(page.page_content for page in pages)
        initial_state: AgentState = {
            "raw_text": content,
            "structured_data": None,
            "status": "",
            "audit_remarks": "",
            "human_feedback": "",
        }
        background_tasks.add_task(run_graph, initial_state)
        return {"result": content}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
