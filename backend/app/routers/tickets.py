from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import ActorDep, AgentDep, SessionDep
from app.models import MessageType, TicketCategory, TicketPriority, TicketStatus
from app.schemas import (
    MessageCreate,
    MessageRead,
    TicketCreate,
    TicketDetail,
    TicketList,
    TicketRead,
    TicketUpdate,
)
from app.realtime import notify
from app.services import tickets as service

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, session: SessionDep, actor: ActorDep):
    """Open a new ticket. It always starts in OPEN and gets a number like BD-1001."""
    return service.create_ticket(session, data, actor)


@router.get("", response_model=TicketList)
def list_tickets(
    session: SessionDep,
    actor: ActorDep,
    status_: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
    category: TicketCategory | None = None,
    assignee_id: int | None = None,
    unassigned: bool = False,
    q: Annotated[str | None, Query(max_length=100, description="Search number, subject, email, order id")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List tickets, newest activity first. Customers only ever see their own."""
    items, total = service.list_tickets(
        session,
        actor,
        status_=status_,
        priority=priority,
        category=category,
        assignee_id=assignee_id,
        unassigned=unassigned,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TicketList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, session: SessionDep, actor: ActorDep):
    """Ticket with its conversation. Internal notes and audit history are agent-only."""
    ticket = service.get_ticket_or_404(session, ticket_id, actor)
    detail = TicketDetail.model_validate(ticket)
    if not actor.is_agent:
        detail.messages = [m for m in detail.messages if m.type == MessageType.PUBLIC]
        detail.events = []
    return detail


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: int, data: TicketUpdate, session: SessionDep, actor: AgentDep):
    """Agents only: change status, priority and/or assignee. Each change is audited."""
    ticket = service.get_ticket_or_404(session, ticket_id, actor)
    updated = service.update_ticket(session, ticket, data, actor)
    notify(ticket_id, "ticket.updated")
    return updated


@router.post("/{ticket_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def add_message(ticket_id: int, data: MessageCreate, session: SessionDep, actor: ActorDep):
    """Add a customer-visible reply, or (agents only) an INTERNAL note."""
    ticket = service.get_ticket_or_404(session, ticket_id, actor)
    message = service.add_message(session, ticket, data, actor)
    # Internal notes are only announced to agents.
    notify(ticket_id, "message.created", agents_only=message.type == MessageType.INTERNAL)
    return message
