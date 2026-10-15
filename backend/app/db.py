from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.config import settings

# One engine for the whole app; it manages a pool of connections to PostgreSQL.
engine = create_engine(settings.database_url)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: opens a DB session per request and always closes it."""
    with Session(engine) as session:
        yield session
