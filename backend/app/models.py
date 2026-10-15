"""Database tables.

Design notes:
- Customers are identified by email on the ticket (no customer accounts yet).
- Agents are a real table, so a ticket can be assigned to one.
- Enums are stored as VARCHAR (native_enum=False) so adding a new category
  or status later does not need an ALTER TYPE migration in PostgreSQL.
"""

from datetime import datetime, timezone
from enum import Enum

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enum_column(enum_cls: type[Enum]) -> sa.Enum:
    return sa.Enum(enum_cls, native_enum=False, length=32)


# ---------- Enums ----------

class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    WAITING_FOR_PROVIDER = "WAITING_FOR_PROVIDER"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TicketCategory(str, Enum):
    INSTALLATION = "INSTALLATION"
    ACTIVATION = "ACTIVATION"
    CONNECTIVITY = "CONNECTIVITY"
    ORDER = "ORDER"
    TOPUP = "TOPUP"
    REFUND = "REFUND"
    OTHER = "OTHER"


class SenderType(str, Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"


class MessageType(str, Enum):
    PUBLIC = "PUBLIC"      # visible to the customer
    INTERNAL = "INTERNAL"  # agent-only note, never shown to the customer


class EventType(str, Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    ASSIGNEE_CHANGED = "ASSIGNEE_CHANGED"


# ---------- Tables ----------

class Agent(SQLModel, table=True):
    __tablename__ = "agents"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=255, unique=True)


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    id: int | None = Field(default=None, primary_key=True)
    # Readable number like BD-1001. Filled by PostgreSQL from a sequence,
    # so two tickets created at the same moment can never get the same number.
    number: str | None = Field(
        default=None,
        max_length=20,
        unique=True,
        nullable=False,
        sa_column_kwargs={"server_default": sa.text("'BD-' || nextval('ticket_number_seq')")},
    )
    customer_email: str = Field(max_length=255, index=True)
    order_id: str | None = Field(default=None, max_length=50)
    category: TicketCategory = Field(sa_type=enum_column(TicketCategory), index=True)
    subject: str = Field(max_length=200)
    description: str = Field(sa_type=sa.Text)
    priority: TicketPriority = Field(
        default=TicketPriority.MEDIUM, sa_type=enum_column(TicketPriority), index=True
    )
    status: TicketStatus = Field(
        default=TicketStatus.OPEN, sa_type=enum_column(TicketStatus), index=True
    )
    assignee_id: int | None = Field(default=None, foreign_key="agents.id", index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    # Python-side links (no extra columns): ticket.assignee, ticket.messages, ticket.events
    assignee: Agent | None = Relationship()
    messages: list["TicketMessage"] = Relationship(
        sa_relationship_kwargs={"order_by": "TicketMessage.created_at"}
    )
    events: list["TicketEvent"] = Relationship(
        sa_relationship_kwargs={"order_by": "TicketEvent.created_at"}
    )


class TicketMessage(SQLModel, table=True):
    __tablename__ = "ticket_messages"
    __table_args__ = (sa.Index("ix_ticket_messages_ticket_created", "ticket_id", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="tickets.id", ondelete="CASCADE")
    sender_type: SenderType = Field(sa_type=enum_column(SenderType))
    # Set when an agent wrote the message; NULL when the customer wrote it.
    sender_agent_id: int | None = Field(default=None, foreign_key="agents.id")
    type: MessageType = Field(default=MessageType.PUBLIC, sa_type=enum_column(MessageType))
    body: str = Field(sa_type=sa.Text)
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    sender_agent: Agent | None = Relationship()


class TicketEvent(SQLModel, table=True):
    """Audit trail: one row per important change. Rows are only ever inserted."""

    __tablename__ = "ticket_events"
    __table_args__ = (sa.Index("ix_ticket_events_ticket_created", "ticket_id", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="tickets.id", ondelete="CASCADE")
    type: EventType = Field(sa_type=enum_column(EventType))
    old_value: str | None = Field(default=None, max_length=100)
    new_value: str | None = Field(default=None, max_length=100)
    # Who made the change (NULL = customer or system).
    actor_agent_id: int | None = Field(default=None, foreign_key="agents.id")
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    actor_agent: Agent | None = Relationship()
