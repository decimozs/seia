from typing import Optional

from typing_extensions import TypedDict

from app.schemas.expense import ExpenseReport


class AgentState(TypedDict):
    raw_text: str
    structured_data: Optional[ExpenseReport]
    status: str
    audit_remarks: str
    human_feedback: Optional[str]
