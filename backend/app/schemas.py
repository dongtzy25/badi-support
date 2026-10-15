"""Request and response shapes for the API (Pydantic).

Kept separate from the table models so the API contract can differ from the
database: e.g. clients can never send `number`, `status` on create, or `id`.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.models import (
    EventType,
    MessageType,
    SenderType,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)

# Reusable string types: whitespace is trimmed before the length is checked,
# so "   " is rejected as empty.
Subject = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
OrderId = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{3,50}$")
]


class StrictModel(BaseModel):
    # Unknown fields are an error, so typos like "priorty" are reported, not ignored.
    model_config = ConfigDict(extra="forbid")


# ---------- Requests ----------

class TicketCreate(StrictModel):
    customer_email: EmailStr
    order_id: OrderId | None = None
    category: TicketCategory
    subject: Subject
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)]
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketUpdate(StrictModel):
    """All fields optional; only the fields actually sent are changed.
    `assignee_id: null` means "unassign", which is different from not sending it."""

    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: int | None = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Send at least one of: status, priority, assignee_id")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        if "priority" in self.model_fields_set and self.priority is None:
            raise ValueError("priority cannot be null")
        return self


class MessageCreate(StrictModel):
    body: LongText
    type: MessageType = MessageType.PUBLIC


# ---------- Responses ----------

class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # build from SQLModel objects


class AgentRead(ReadModel):
    id: int
    name: str
    email: str


class TicketRead(ReadModel):
    id: int
    number: str
    customer_email: str
    order_id: str | None
    category: TicketCategory
    subject: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    assignee: AgentRead | None
    created_at: datetime
    updated_at: datetime


class TicketList(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int


class MessageRead(ReadModel):
    id: int
    ticket_id: int
    sender_type: SenderType
    sender_agent: AgentRead | None
    type: MessageType
    body: str
    created_at: datetime


class EventRead(ReadModel):
    id: int
    type: EventType
    old_value: str | None
    new_value: str | None
    actor_agent: AgentRead | None
    created_at: datetime


class TicketDetail(TicketRead):
    messages: list[MessageRead]
    events: list[EventRead]  # empty for customers


class OrderSummary(BaseModel):
    order_id: str
    destination: str
    package: str
    status: str
    esim_status: str
