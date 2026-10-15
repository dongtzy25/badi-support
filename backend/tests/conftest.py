"""Test setup.

Tests run against a REAL PostgreSQL database (not SQLite), because the app
relies on PostgreSQL features: the ticket-number sequence, timezone-aware
timestamps and ILIKE search. A separate database is used so tests never touch
your demo data:

  TEST_DATABASE_URL, if set, otherwise DATABASE_URL with "_test" added to the
  database name (badi_support -> badi_support_test). It is created if missing.

Once per test run the migrations are applied from scratch (downgrade to empty,
then upgrade to head), so the migration files are tested too. Before each test
every table is emptied and ticket numbers restart at BD-1001.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, make_url, text

from app.config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


TEST_URL = _test_database_url()

# Point the whole app (engine, Alembic) at the test database BEFORE app.db is imported.
settings.database_url = TEST_URL

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Agent  # noqa: E402


def _create_database_if_missing() -> None:
    url = make_url(TEST_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    from alembic import command
    from alembic.config import Config

    _create_database_if_missing()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ticket_events, ticket_messages, tickets, agents RESTART IDENTITY CASCADE"))
        conn.execute(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1001"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def agents():
    """Two agents: ids 1 (Anas) and 2 (Maria)."""
    with Session(engine) as s:
        s.add_all([Agent(name="Anas", email="anas@badi.example"), Agent(name="Maria", email="maria@badi.example")])
        s.commit()


AGENT = {"X-Role": "agent", "X-Agent-Id": "1"}
CUSTOMER = {"X-Role": "customer", "X-Customer-Email": "customer@example.com"}
OTHER_CUSTOMER = {"X-Role": "customer", "X-Customer-Email": "someone.else@example.com"}

TICKET = {
    "customer_email": "customer@example.com",
    "order_id": "ORD-10293",
    "category": "CONNECTIVITY",
    "subject": "eSIM installed but no internet",
    "description": "My eSIM is installed but internet is not working.",
    "priority": "HIGH",
}


@pytest.fixture
def ticket(client, agents) -> dict:
    """One ticket opened by the customer."""
    response = client.post("/tickets", json=TICKET, headers=CUSTOMER)
    assert response.status_code == 201, response.text
    return response.json()
