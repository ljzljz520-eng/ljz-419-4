from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TicketCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    priority: str = "medium"


class AssignIn(BaseModel):
    assignee_id: int


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    priority: str
    creator_id: int
    assignee_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class TicketListOut(BaseModel):
    tickets: List[TicketOut]
