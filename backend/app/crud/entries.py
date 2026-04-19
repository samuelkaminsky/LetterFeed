from datetime import datetime, timedelta

from nanoid import generate
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import get_logger
from app.models.entries import Entry
from app.schemas.entries import EntryCreate

logger = get_logger(__name__)


def get_all_entries(db: Session, skip: int = 0, limit: int | None = None):
    """Retrieve all entries from all newsletters, sorted by received date."""
    logger.debug(f"Querying all entries with skip={skip}, limit={limit}")
    query = (
        db.query(Entry)
        .options(joinedload(Entry.newsletter))
        .order_by(Entry.received_at.desc())
    )

    if settings.feed_retention_days is not None:
        cutoff_date = datetime.now() - timedelta(days=settings.feed_retention_days)
        query = query.filter(Entry.received_at >= cutoff_date)

    query = query.offset(skip)

    if limit is not None:
        query = query.limit(limit)
    return query.all()


def get_entries_by_newsletter(
    db: Session, newsletter_id: str, skip: int = 0, limit: int | None = None
):
    """Retrieve entries for a specific newsletter."""
    logger.debug(
        f"Querying entries for newsletter_id={newsletter_id}, skip={skip}, limit={limit}"
    )
    query = (
        db.query(Entry)
        .order_by(Entry.received_at.desc())
        .filter(Entry.newsletter_id == newsletter_id)
    )

    if settings.feed_retention_days is not None:
        cutoff_date = datetime.now() - timedelta(days=settings.feed_retention_days)
        query = query.filter(Entry.received_at >= cutoff_date)

    query = query.offset(skip)

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def get_entry_by_message_id(db: Session, message_id: str):
    """Retrieve an entry by its message_id."""
    logger.debug(f"Querying for entry with message_id={message_id}")
    return db.query(Entry).filter(Entry.message_id == message_id).first()


def get_latest_entry_timestamp(
    db: Session, newsletter_id: str | None = None
) -> datetime | None:
    """Retrieve the timestamp of the latest entry."""
    query = db.query(Entry.received_at).order_by(Entry.received_at.desc())
    if newsletter_id:
        query = query.filter(Entry.newsletter_id == newsletter_id)
    result = query.first()
    return result[0] if result else None


def create_entry(db: Session, entry: EntryCreate, newsletter_id: str):
    """Create a new entry for a newsletter."""
    logger.info(
        f"Creating new entry for newsletter_id={newsletter_id} with subject '{entry.subject}'"
    )
    db_entry = Entry(id=generate(), **entry.model_dump(), newsletter_id=newsletter_id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    logger.info(f"Successfully created entry with id={db_entry.id}")
    return db_entry
