import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import auth_client
from .db import get_db
from .models import PRIORITIES, STATUS_ASSIGNED, STATUS_CLOSED, STATUS_OPEN, Ticket
from .observability import TraceMiddleware, setup_logging
from .schemas import AssignIn, TicketCreateIn, TicketListOut, TicketOut

setup_logging("ticket")
logger = logging.getLogger("ticket")

app = FastAPI(title="ticket-service", version="1.0.0")
app.add_middleware(TraceMiddleware)


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return await auth_client.verify_token(authorization)


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin", "agent"):
        raise HTTPException(status_code=403, detail="admin or agent role required")
    return user


def get_ticket_or_404(ticket_id: int, db: Session) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return ticket


def can_view(ticket: Ticket, user: dict) -> bool:
    if user["role"] in ("admin", "agent"):
        return True
    return ticket.creator_id == user["id"] or ticket.assignee_id == user["id"]


@app.get("/health")
def health():
    return {"status": "ok", "service": "ticket"}


@app.post("/tickets", response_model=TicketOut, status_code=201)
def create_ticket(
    body: TicketCreateIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.priority not in PRIORITIES:
        raise HTTPException(status_code=400, detail="invalid priority: " + body.priority)
    ticket = Ticket(
        title=body.title,
        description=body.description,
        priority=body.priority,
        status=STATUS_OPEN,
        creator_id=user["id"],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    logger.info("ticket created id=%s creator=%s title=%r", ticket.id, user["id"], ticket.title)
    return ticket


@app.get("/tickets", response_model=TicketListOut)
def list_tickets(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = db.query(Ticket)
    if user["role"] not in ("admin", "agent"):
        query = query.filter(
            or_(Ticket.creator_id == user["id"], Ticket.assignee_id == user["id"])
        )
    if status:
        query = query.filter(Ticket.status == status)
    tickets = query.order_by(Ticket.id.desc()).all()
    logger.info("tickets listed user=%s count=%s", user["id"], len(tickets))
    return TicketListOut(tickets=tickets)


@app.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ticket = get_ticket_or_404(ticket_id, db)
    if not can_view(ticket, user):
        raise HTTPException(status_code=403, detail="not allowed to view this ticket")
    return ticket


@app.post("/tickets/{ticket_id}/assign", response_model=TicketOut)
async def assign_ticket(
    ticket_id: int,
    body: AssignIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
    user: dict = Depends(require_staff),
):
    ticket = get_ticket_or_404(ticket_id, db)
    if ticket.status == STATUS_CLOSED:
        raise HTTPException(status_code=409, detail="cannot assign a closed ticket")
    assignee = await auth_client.fetch_user(body.assignee_id, authorization)
    if assignee["role"] not in ("admin", "agent"):
        raise HTTPException(status_code=400, detail="assignee must be an agent or admin")
    ticket.assignee_id = body.assignee_id
    ticket.status = STATUS_ASSIGNED
    db.commit()
    db.refresh(ticket)
    logger.info("ticket assigned id=%s assignee=%s by=%s", ticket.id, body.assignee_id, user["id"])
    return ticket


@app.post("/tickets/{ticket_id}/close", response_model=TicketOut)
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ticket = get_ticket_or_404(ticket_id, db)
    if ticket.status == STATUS_CLOSED:
        raise HTTPException(status_code=409, detail="ticket already closed")
    is_owner = ticket.creator_id == user["id"] or ticket.assignee_id == user["id"]
    if user["role"] != "admin" and not is_owner:
        raise HTTPException(status_code=403, detail="not allowed to close this ticket")
    ticket.status = STATUS_CLOSED
    db.commit()
    db.refresh(ticket)
    logger.info("ticket closed id=%s by=%s", ticket.id, user["id"])
    return ticket
