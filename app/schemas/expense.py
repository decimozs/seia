from typing import Optional

from pydantic import BaseModel, Field


class ExpenseReport(BaseModel):
    merchant: str = Field(description="Name of the vendor or store")
    date: Optional[str] = Field(
        description="Date of the transaction in YYYY-MM-DD format"
    )
    amount: float = Field(description="Total amount spent")
    currency: str = Field(description="Currency code, e.g., PHP, USD")
    category: str = Field(description="Type of expense (e.g., Meals, Travel, Supplies)")
