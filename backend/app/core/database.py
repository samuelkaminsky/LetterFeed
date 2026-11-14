"""Database connection and session management."""

from collections.abc import Iterator
from typing import Protocol

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


class _DBAPICursor(Protocol):
    def execute(self, sql: str) -> object: ...
    def close(self) -> None: ...


class _DBAPIConnection(Protocol):
    def cursor(self) -> _DBAPICursor: ...


@event.listens_for(engine, "connect")
def set_sqlite_pragma(
    dbapi_connection: _DBAPIConnection, connection_record: object
) -> None:
    """Enable SQLite WAL, foreign keys, busy timeout, and synchronous=NORMAL on connect."""
    if settings.database_url.startswith("sqlite"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
            logger.debug(
                "SQLite pragmas enabled (WAL, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000)."
            )
        except Exception as e:
            logger.error(f"Failed to enable SQLite pragmas: {e}")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Iterator[Session]:
    """Yield a database session."""
    logger.debug("Creating new database session")
    db = SessionLocal()
    try:
        yield db
    finally:
        logger.debug("Closing database session")
        db.close()
