from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from app.node import audit_node, extract_node, human_review_node, output_node
from app.state import AgentState


def route_after_audit(state: AgentState) -> str:
    if state["status"] == "approved":
        return "output"
    return "human_review"


builder = StateGraph(AgentState)
builder.add_node("extract", extract_node)
builder.add_node("audit", audit_node)
builder.add_node("human_review", human_review_node)
builder.add_node("output", output_node)

builder.set_entry_point("extract")
builder.add_edge("extract", "audit")
builder.add_conditional_edges(
    "audit",
    route_after_audit,
    {
        "output": "output",
        "human_review": "human_review",
    },
)
builder.add_edge("human_review", "output")
builder.add_edge("output", END)


graph = builder.compile(checkpointer=InMemorySaver())
