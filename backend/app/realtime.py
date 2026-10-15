"""Real-time updates over WebSockets.

Each open ticket screen connects to  /ws/tickets/{id}  and is put in that
ticket's "room". When something changes, the API sends a small event to the
room, e.g. {"type": "message.created", "ticket_id": 1}. The browser then
re-fetches the ticket over normal REST.

Why send a signal and not the full data? The REST endpoint already applies
the visibility rules (internal notes hidden from customers), so there is only
one place that decides what a customer may see.

Internal notes are only signalled to agents, so customers don't even learn
that a note was added.

Limitation: rooms live in this process's memory, so this works with one API
process. With several processes you'd fan out through Redis pub/sub or
PostgreSQL LISTEN/NOTIFY instead.
"""

from collections import defaultdict
from dataclasses import dataclass

import anyio
from fastapi import WebSocket


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    is_agent: bool


class TicketRooms:
    def __init__(self) -> None:
        self._rooms: dict[int, set[Connection]] = defaultdict(set)

    def join(self, ticket_id: int, conn: Connection) -> None:
        self._rooms[ticket_id].add(conn)

    def leave(self, ticket_id: int, conn: Connection) -> None:
        self._rooms[ticket_id].discard(conn)
        if not self._rooms[ticket_id]:
            del self._rooms[ticket_id]

    async def broadcast(self, ticket_id: int, event: dict, agents_only: bool = False) -> None:
        for conn in list(self._rooms.get(ticket_id, ())):
            if agents_only and not conn.is_agent:
                continue
            try:
                await conn.websocket.send_json(event)
            except Exception:
                self.leave(ticket_id, conn)  # browser tab closed mid-send


rooms = TicketRooms()


def notify(ticket_id: int, event_type: str, agents_only: bool = False) -> None:
    """Call from normal (sync) endpoints. FastAPI runs those in a worker thread,
    so we hop back onto the event loop to send on the WebSockets."""
    event = {"type": event_type, "ticket_id": ticket_id}
    try:
        anyio.from_thread.run(rooms.broadcast, ticket_id, event, agents_only)
    except RuntimeError:
        pass  # not inside a FastAPI worker thread (e.g. seed script): nobody to notify
