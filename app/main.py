import os
import shutil
import tempfile
import uuid
from typing import Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from langchain_community.document_loaders import PyPDFLoader

from app.agent import graph
from app.state import AgentState

app = FastAPI()

results_store: Dict[str, dict] = {}

config_template = {"configurable": {"thread_id": ""}}


def run_langgraph_agent(task_id: str, content: str):
    """
    Worker function that runs the LangGraph process in the background.
    """
    try:
        initial_state: AgentState = {
            "raw_text": content,
            "structured_data": None,
            "status": "processing",
            "audit_remarks": "",
            "human_feedback": "",
        }
        current_config = {"configurable": {"thread_id": task_id}}
        result = graph.invoke(initial_state, config=current_config)
        results_store[task_id] = {"status": "completed", "result": result}
    except Exception as e:
        print(f"Error processing task {task_id}: {str(e)}")
        results_store[task_id] = {"status": "failed", "error": str(e)}


@app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}


@app.post("/process-invoice")
async def process_invoice(request: Request, background_tasks: BackgroundTasks):
    # 1. Extract file from form data
    form = await request.form()
    if not form:
        raise HTTPException(status_code=400, detail="No form data received")

    file = next(iter(form.values()))
    task_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        shutil.copyfileobj(file.file, temp_pdf)
        temp_path = temp_pdf.name

    try:
        loader = PyPDFLoader(temp_path)
        pages = loader.load()
        content = "\n\n".join(page.page_content for page in pages)

        results_store[task_id] = {"status": "pending"}
        background_tasks.add_task(run_langgraph_agent, task_id, content)

        return {
            "task_id": task_id,
            "status": "accepted",
            "check_url": f"/status/{task_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to initiate processing: {str(e)}"
        )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    status_data = results_store.get(task_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Task ID not found")

    return status_data
