from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlmodel import Session

from app.db import engine
from app.models import Agent, Ticket
from app.realtime import Connection, rooms

router = APIRouter()


@router.websocket("/ws/tickets/{ticket_id}")
async def ticket_updates(
    websocket: WebSocket,
    ticket_id: int,
    role: str,
    agent_id: int | None = None,
    email: str | None = None,
):
    """Browsers can't set custom headers on a WebSocket, so the identity comes
    in the query string: ?role=agent&agent_id=1  or  ?role=customer&email=..."""
    # Same access rules as GET /tickets/{id}, checked once when connecting.
    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        if role == "agent":
            allowed = ticket is not None and agent_id is not None and session.get(Agent, agent_id) is not None
        elif role == "customer":
            allowed = ticket is not None and bool(email) and ticket.customer_email == email.strip().lower()
        else:
            allowed = False
    if not allowed:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    conn = Connection(websocket=websocket, is_agent=role == "agent")
    rooms.join(ticket_id, conn)
    try:
        while True:
            await websocket.receive_text()  # we don't expect messages; this just waits for disconnect
    except WebSocketDisconnect:
        pass
    finally:
        rooms.leave(ticket_id, conn)
