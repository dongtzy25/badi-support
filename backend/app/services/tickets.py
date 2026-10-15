"""Ticket business rules.

Routers handle HTTP (parsing, status codes); this module holds the rules, so
they can be tested and reused (e.g. by the WebSocket code later).
Every change that matters is written to ticket_events in the SAME transaction
as the change itself, so the audit trail can never miss an update.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.deps import Actor
from app.models import (
    Agent,
    EventType,
    MessageType,
    SenderType,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketMessage,
    TicketPriority,
    TicketStatus,
    utcnow,
)
from app.schemas import MessageCreate, TicketCreate, TicketUpdate

# A customer reply on a ticket in one of these states moves it back to IN_PROGRESS,
# because the ball is now in support's court again.
REOPEN_ON_CUSTOMER_REPLY = {TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.RESOLVED}


def _event(ticket: Ticket, type_: EventType, old, new, actor: Actor | None) -> TicketEvent:
    return TicketEvent(
        ticket_id=ticket.id,
        type=type_,
        old_value=None if old is None else str(getattr(old, "value", old)),
        new_value=None if new is None else str(getattr(new, "value", new)),
        actor_agent_id=actor.agent.id if actor and actor.agent else None,
    )


def get_ticket_or_404(session: Session, ticket_id: int, actor: Actor) -> Ticket:
    ticket = session.get(Ticket, ticket_id)
    # Customers get 404 (not 403) for other people's tickets, so they cannot
    # discover which ticket ids exist.
    if ticket is None or (not actor.is_agent and ticket.customer_email != actor.email):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ticket {ticket_id} not found")
    return ticket


def create_ticket(session: Session, data: TicketCreate, actor: Actor) -> Ticket:
    email = data.customer_email.lower()
    if not actor.is_agent and email != actor.email:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers can only open tickets for their own email")

    ticket = Ticket(**data.model_dump(exclude={"customer_email"}), customer_email=email)
    session.add(ticket)
    session.flush()  # sends the INSERT so PostgreSQL fills in id and number (BD-xxxx)
    session.add(_event(ticket, EventType.CREATED, None, ticket.status, actor))
    session.commit()
    session.refresh(ticket)
    return ticket


def list_tickets(
    session: Session,
    actor: Actor,
    *,
    status_: TicketStatus | None,
    priority: TicketPriority | None,
    category: TicketCategory | None,
    assignee_id: int | None,
    unassigned: bool,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Ticket], int]:
    filters = []
    if not actor.is_agent:
        filters.append(Ticket.customer_email == actor.email)
    if status_:
        filters.append(Ticket.status == status_)
    if priority:
        filters.append(Ticket.priority == priority)
    if category:
        filters.append(Ticket.category == category)
    if unassigned:
        filters.append(Ticket.assignee_id.is_(None))
    elif assignee_id is not None:
        filters.append(Ticket.assignee_id == assignee_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Ticket.number.ilike(like),
                Ticket.subject.ilike(like),
                Ticket.customer_email.ilike(like),
                Ticket.order_id.ilike(like),
            )
        )

    total = session.exec(select(func.count()).select_from(Ticket).where(*filters)).one()
    rows = session.exec(
        select(Ticket)
        .where(*filters)
        .options(selectinload(Ticket.assignee))
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def update_ticket(session: Session, ticket: Ticket, data: TicketUpdate, actor: Actor) -> Ticket:
    changes = data.model_dump(exclude_unset=True)  # only the fields the client sent
    events: list[TicketEvent] = []

    if "status" in changes and changes["status"] != ticket.status:
        events.append(_event(ticket, EventType.STATUS_CHANGED, ticket.status, changes["status"], actor))
        ticket.status = changes["status"]

    if "priority" in changes and changes["priority"] != ticket.priority:
        events.append(_event(ticket, EventType.PRIORITY_CHANGED, ticket.priority, changes["priority"], actor))
        ticket.priority = changes["priority"]

    if "assignee_id" in changes and changes["assignee_id"] != ticket.assignee_id:
        new_id = changes["assignee_id"]
        new_agent = session.get(Agent, new_id) if new_id is not None else None
        if new_id is not None and new_agent is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Agent {new_id} does not exist")
        old_name = ticket.assignee.name if ticket.assignee else None
        events.append(
            _event(ticket, EventType.ASSIGNEE_CHANGED, old_name, new_agent.name if new_agent else None, actor)
        )
        ticket.assignee_id = new_id

    if events:  # nothing changed -> nothing to save or audit
        ticket.updated_at = utcnow()
        session.add(ticket)
        session.add_all(events)
        session.commit()
        session.refresh(ticket)
    return ticket


def add_message(session: Session, ticket: Ticket, data: MessageCreate, actor: Actor) -> TicketMessage:
    if data.type == MessageType.INTERNAL and not actor.is_agent:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only support agents can add internal notes")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ticket {ticket.number} is closed. Reopen it before adding messages."
        )

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_type=SenderType.AGENT if actor.is_agent else SenderType.CUSTOMER,
        sender_agent_id=actor.agent.id if actor.agent else None,
        type=data.type,
        body=data.body,
    )
    session.add(message)

    if not actor.is_agent and ticket.status in REOPEN_ON_CUSTOMER_REPLY:
        session.add(_event(ticket, EventType.STATUS_CHANGED, ticket.status, TicketStatus.IN_PROGRESS, None))
        ticket.status = TicketStatus.IN_PROGRESS

    ticket.updated_at = utcnow()
    session.add(ticket)
    session.commit()
    session.refresh(message)
    return message
