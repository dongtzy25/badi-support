"""Demo data.

  python -m app.seed             reset: deletes ALL tickets and agents, then inserts the demo data
                                 (ticket numbers restart at BD-1001)
  python -m app.seed --if-empty  only seed when there are no agents yet (used by Docker on start-up,
                                 so restarting the containers never wipes your data)
"""

import sys

from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session, func, select

from app.db import engine
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


def seed() -> None:
    now = utcnow()
    ago = lambda **kw: now - timedelta(**kw)  # noqa: E731

    with Session(engine) as s:
        s.exec(text("TRUNCATE ticket_events, ticket_messages, tickets, agents RESTART IDENTITY CASCADE"))
        s.exec(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1001"))

        anas = Agent(name="Anas", email="anas@badi.example")
        maria = Agent(name="Maria", email="maria@badi.example")
        joel = Agent(name="Joel", email="joel@badi.example")
        s.add_all([anas, maria, joel])
        s.flush()

        def ticket(created, **kw) -> Ticket:
            t = Ticket(created_at=created, updated_at=created, **kw)
            s.add(t)
            s.flush()
            s.add(TicketEvent(ticket_id=t.id, type=EventType.CREATED, new_value="OPEN", created_at=created))
            return t

        def msg(t, at, body, agent=None, internal=False):
            s.add(TicketMessage(
                ticket_id=t.id, created_at=at, body=body,
                sender_type=SenderType.AGENT if agent else SenderType.CUSTOMER,
                sender_agent_id=agent.id if agent else None,
                type=MessageType.INTERNAL if internal else MessageType.PUBLIC,
            ))
            t.updated_at = max(t.updated_at, at)

        def event(t, at, type_, old, new, agent):
            s.add(TicketEvent(ticket_id=t.id, type=type_, old_value=old, new_value=new,
                              actor_agent_id=agent.id, created_at=at))
            t.updated_at = max(t.updated_at, at)

        # The ticket description is the customer's opening message, so it is not
        # repeated in ticket_messages; the UI shows it at the top of the thread.

        # BD-1001: the example from the assignment brief
        t1 = ticket(ago(hours=3), customer_email="customer@example.com", order_id="ORD-10293",
                    category=TicketCategory.CONNECTIVITY, subject="eSIM installed but no internet",
                    description="My eSIM is installed but internet is not working.",
                    priority=TicketPriority.HIGH, status=TicketStatus.WAITING_FOR_PROVIDER, assignee_id=anas.id)
        msg(t1, ago(hours=2, minutes=55), "Are you currently in Turkey?", agent=anas)
        event(t1, ago(hours=2, minutes=54), EventType.STATUS_CHANGED, "OPEN", "IN_PROGRESS", anas)
        event(t1, ago(hours=2, minutes=53), EventType.ASSIGNEE_CHANGED, None, "Anas", anas)
        msg(t1, ago(hours=2, minutes=50), "Yes.")
        msg(t1, ago(hours=2, minutes=46), "Escalated to upstream provider for status verification.",
            agent=anas, internal=True)
        event(t1, ago(hours=2, minutes=45), EventType.STATUS_CHANGED, "IN_PROGRESS", "WAITING_FOR_PROVIDER", anas)

        # BD-1002: new and unassigned
        t2 = ticket(ago(minutes=40), customer_email="lea@example.com", order_id="ORD-10310",
                    category=TicketCategory.INSTALLATION, subject="QR code does not scan on my iPhone",
                    description="When I scan the QR code the camera says 'No usable data found'.",
                    priority=TicketPriority.MEDIUM)

        # BD-1003: waiting for the customer
        t3 = ticket(ago(days=1), customer_email="customer@example.com", order_id="ORD-10342",
                    category=TicketCategory.REFUND, subject="Refund for unused plan",
                    description="I bought the wrong plan and have not installed it. Can I get a refund?",
                    priority=TicketPriority.LOW, status=TicketStatus.WAITING_FOR_CUSTOMER, assignee_id=maria.id)
        msg(t3, ago(hours=20), "Sure! Can you confirm the email used at checkout?", agent=maria)
        event(t3, ago(hours=20), EventType.ASSIGNEE_CHANGED, None, "Maria", maria)
        event(t3, ago(hours=20), EventType.STATUS_CHANGED, "OPEN", "WAITING_FOR_CUSTOMER", maria)

        # BD-1004: urgent, in progress
        t4 = ticket(ago(hours=1), customer_email="ken@example.com", category=TicketCategory.ACTIVATION,
                    subject="Activation stuck at 'pending' before flight",
                    description="My flight leaves in 3 hours and the eSIM still shows pending activation.",
                    priority=TicketPriority.URGENT, status=TicketStatus.IN_PROGRESS, assignee_id=joel.id)
        event(t4, ago(minutes=50), EventType.STATUS_CHANGED, "OPEN", "IN_PROGRESS", joel)

        # BD-1005: resolved
        t5 = ticket(ago(days=3), customer_email="sam@example.com", category=TicketCategory.TOPUP,
                    subject="Top-up paid but data not added",
                    description="I paid for a 3 GB top-up but my balance did not change.",
                    priority=TicketPriority.MEDIUM, status=TicketStatus.RESOLVED, assignee_id=anas.id)
        msg(t5, ago(days=2), "The top-up is now applied. Please restart your phone.", agent=anas)
        event(t5, ago(days=2), EventType.STATUS_CHANGED, "OPEN", "RESOLVED", anas)

        s.add_all([t1, t2, t3, t4, t5])
        s.commit()
    print("Seeded 3 agents and 5 tickets (BD-1001 .. BD-1005).")


def has_data() -> bool:
    with Session(engine) as s:
        return s.exec(select(func.count()).select_from(Agent)).one() > 0


if __name__ == "__main__":
    if "--if-empty" in sys.argv and has_data():
        print("Database already has data; skipping seed.")
    else:
        seed()
