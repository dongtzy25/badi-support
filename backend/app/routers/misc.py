from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.deps import SessionDep
from app.models import Agent
from app.schemas import AgentRead, OrderSummary

router = APIRouter()


@router.get("/agents", response_model=list[AgentRead], tags=["agents"])
def list_agents(session: SessionDep):
    """Agents, for the assignee dropdown and the demo identity picker.
    Public only because there is no real login yet; with auth it would require one."""
    return session.exec(select(Agent).order_by(Agent.name)).all()


# Stand-in for the real orders service; no eSIM provider integration needed.
MOCK_ORDERS = {
    "ORD-10293": {"destination": "Turkey", "package": "10 GB", "status": "completed", "esim_status": "installed"},
    "ORD-10310": {"destination": "Japan", "package": "5 GB", "status": "completed", "esim_status": "not_installed"},
    "ORD-10342": {"destination": "Philippines", "package": "20 GB", "status": "refund_requested", "esim_status": "active"},
}


@router.get("/mock/orders/{order_id}", response_model=OrderSummary, tags=["mock"])
def get_mock_order(order_id: str):
    order = MOCK_ORDERS.get(order_id.upper())
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order {order_id} not found")
    return OrderSummary(order_id=order_id.upper(), **order)
