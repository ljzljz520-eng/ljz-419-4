from sqlalchemy import Column, DateTime, Integer, String, Text, func

from .db import Base

STATUS_OPEN = "open"
STATUS_ASSIGNED = "assigned"
STATUS_CLOSED = "closed"

PRIORITIES = ("low", "medium", "high", "urgent")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(String(16), nullable=False, default=STATUS_OPEN)
    priority = Column(String(16), nullable=False, default="medium")
    creator_id = Column(Integer, nullable=False, index=True)
    assignee_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
