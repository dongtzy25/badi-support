"""Who is making the request?

There is no real login in this assignment, so the caller says who they are with
headers. This is NOT security (anyone can send any header); it lets the API
enforce role rules now, and later the headers can be replaced by a JWT/session
check inside `get_actor` without touching any endpoint.

  Agent:     X-Role: agent      X-Agent-Id: 1
  Customer:  X-Role: customer   X-Customer-Email: customer@example.com
"""

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.db import get_session
from app.models import Agent

SessionDep = Annotated[Session, Depends(get_session)]


@dataclass
class Actor:
    role: Literal["agent", "customer"]
    agent: Agent | None = None
    email: str | None = None

    @property
    def is_agent(self) -> bool:
        return self.role == "agent"


def get_actor(
    session: SessionDep,
    x_role: Annotated[Literal["agent", "customer"] | None, Header()] = None,
    x_agent_id: Annotated[int | None, Header()] = None,
    x_customer_email: Annotated[str | None, Header()] = None,
) -> Actor:
    if x_role is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Role header is required (agent or customer)")
    if x_role == "agent":
        if x_agent_id is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Agent-Id header is required for agents")
        agent = session.get(Agent, x_agent_id)
        if agent is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Unknown agent id {x_agent_id}")
        return Actor(role="agent", agent=agent, email=agent.email)

    if not x_customer_email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Customer-Email header is required for customers")
    return Actor(role="customer", email=x_customer_email.strip().lower())


ActorDep = Annotated[Actor, Depends(get_actor)]


def require_agent(actor: ActorDep) -> Actor:
    if not actor.is_agent:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only support agents can do this")
    return actor


AgentDep = Annotated[Actor, Depends(require_agent)]
