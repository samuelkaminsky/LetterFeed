import threading
from collections import OrderedDict
from typing import Literal

from nanoid import generate
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.crud.entries import bump_metadata_version, clear_latest_timestamp_cache
from app.models.entries import Entry
from app.models.newsletters import Newsletter, Sender
from app.schemas.newsletters import NewsletterCreate, NewsletterUpdate

logger = get_logger(__name__)


def get_newsletter_by_identifier(db: Session, identifier: str) -> Newsletter | None:
    """Retrieve a single newsletter by its ID or slug."""
    logger.debug(f"Querying for newsletter with identifier={identifier}")
    result = (
        db.query(Newsletter, func.count(Entry.id))
        .outerjoin(Entry, Newsletter.id == Entry.newsletter_id)
        .filter(or_(Newsletter.id == identifier, Newsletter.slug == identifier))
        .group_by(Newsletter.id)
        .options(selectinload(Newsletter.senders))
        .first()
    )
    if result:
        newsletter, count = result
        newsletter.entries_count = count
        return newsletter
    return None


def get_newsletter_by_slug(db: Session, slug: str) -> Newsletter | None:
    """Retrieve a newsletter by its slug."""
    return db.query(Newsletter).filter(Newsletter.slug == slug).first()


# Cache of identifier -> (id, slug). Newsletter identity is stable between
# metadata changes, so this lets the conditional-request (304) hot path resolve
# a slug/id without touching the DB. Cleared on any newsletter create/update/
# delete (same points that bump the metadata version). Process-local; assumes a
# single worker, like the other in-memory caches. Bounded (LRU eviction): a
# positive entry is only ever a real id/slug, so the key space is already small,
# but the cap keeps it hard-bounded as defense in depth.
_IDENTITY_CACHE_MAX = 1024
_identity_cache: OrderedDict[str, tuple[str, str | None]] = OrderedDict()

# Bounded negative cache of identifiers known not to exist, so a flood of bad
# feed requests doesn't hit the DB on every call. Bounded (LRU eviction) so a
# flood of *distinct* invalid identifiers can't exhaust memory. Cleared whenever
# a newsletter changes, since a previously-missing slug may now be valid.
_MISSING_IDENTITY_CACHE_MAX = 1024
_missing_identity_cache: OrderedDict[str, None] = OrderedDict()

# Sync cache access: sync FastAPI endpoints run in a threadpool, so concurrent
# requests can touch these caches at once. The compound OrderedDict eviction
# (move_to_end / popitem) is not safe to interleave, so guard all access.
_identity_cache_lock = threading.Lock()


def get_newsletter_identity(
    db: Session, identifier: str
) -> tuple[str, str | None] | None:
    """Resolve a newsletter's (id, slug) by id or slug, cached in memory.

    Lightweight alternative to get_newsletter_by_identifier for the feed hot
    path: no entry-count aggregation and no sender load. Both hits and misses are
    cached (misses in a bounded LRU) to keep the path DB-free.
    """
    with _identity_cache_lock:
        if identifier in _identity_cache:
            _identity_cache.move_to_end(identifier)
            return _identity_cache[identifier]
        if identifier in _missing_identity_cache:
            _missing_identity_cache.move_to_end(identifier)
            return None

    # Query outside the lock so DB I/O never blocks other cache readers.
    row = (
        db.query(Newsletter.id, Newsletter.slug)
        .filter(or_(Newsletter.id == identifier, Newsletter.slug == identifier))
        .first()
    )

    with _identity_cache_lock:
        if row is None:
            _missing_identity_cache[identifier] = None
            _missing_identity_cache.move_to_end(identifier)
            while len(_missing_identity_cache) > _MISSING_IDENTITY_CACHE_MAX:
                _missing_identity_cache.popitem(last=False)  # evict least-recent
            return None

        identity = (row.id, row.slug)
        _identity_cache[identifier] = identity
        _identity_cache.move_to_end(identifier)
        while len(_identity_cache) > _IDENTITY_CACHE_MAX:
            _identity_cache.popitem(last=False)  # evict least-recent
        return identity


def clear_identity_cache() -> None:
    """Invalidate both the positive and negative identity caches."""
    with _identity_cache_lock:
        _identity_cache.clear()
        _missing_identity_cache.clear()


def get_newsletters(
    db: Session, skip: int = 0, limit: int | None = None
) -> list[Newsletter]:
    """Retrieve a list of newsletters with entry counts."""
    logger.debug(f"Querying for newsletters with skip={skip}, limit={limit}")
    query = (
        db.query(Newsletter, func.count(Entry.id))
        .outerjoin(Entry, Newsletter.id == Entry.newsletter_id)
        .group_by(Newsletter.id)
        .order_by(Newsletter.id)
        .options(selectinload(Newsletter.senders))
        .offset(skip)
    )
    if limit is not None:
        query = query.limit(limit)
    results = query.all()

    newsletters_with_count = []
    for newsletter, count in results:
        newsletter.entries_count = count
        newsletters_with_count.append(newsletter)

    return newsletters_with_count


def get_all_newsletters_for_processing(db: Session) -> list[Newsletter]:
    """Retrieve all newsletters with senders loaded without entry-count aggregation."""
    return (
        db.query(Newsletter)
        .order_by(Newsletter.id)
        .options(selectinload(Newsletter.senders))
        .all()
    )


def create_newsletter(db: Session, newsletter: NewsletterCreate) -> Newsletter | None:
    """Create a new newsletter."""
    logger.info(f"Creating new newsletter with name '{newsletter.name}'")

    if newsletter.slug and get_newsletter_by_slug(db, newsletter.slug):
        return None  # Indicates a conflict

    try:
        db_newsletter = Newsletter(
            id=generate(size=10),
            name=newsletter.name,
            slug=newsletter.slug,
            search_folder=newsletter.search_folder,
            is_active=newsletter.is_active,
            extract_content=newsletter.extract_content,
            move_to_folder=newsletter.move_to_folder,
        )
        db.add(db_newsletter)
        db.flush()

        for email in newsletter.sender_emails:
            db_sender = Sender(
                id=generate(), email=email.lower(), newsletter_id=db_newsletter.id
            )
            db.add(db_sender)

        db.commit()
        db.refresh(db_newsletter)

        logger.info(f"Successfully created newsletter with id={db_newsletter.id}")
        bump_metadata_version()
        clear_identity_cache()
        db_newsletter.entries_count = 0
        return db_newsletter
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create newsletter: {e}", exc_info=True)
        raise


def update_newsletter(
    db: Session, newsletter_id: str, newsletter_update: NewsletterUpdate
) -> Newsletter | Literal["conflict"] | None:
    """Update an existing newsletter."""
    logger.info(f"Updating newsletter with id={newsletter_id}")
    db_newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
    if not db_newsletter:
        return None

    if newsletter_update.slug:
        existing_newsletter = get_newsletter_by_slug(db, newsletter_update.slug)
        if existing_newsletter and existing_newsletter.id != newsletter_id:
            return "conflict"  # Indicates a conflict

    try:
        update_data = newsletter_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "sender_emails":
                continue
            setattr(db_newsletter, key, value)

        new_emails_lower = {email.lower() for email in newsletter_update.sender_emails}
        existing_emails_lower: set[str] = set()

        # Remove senders that are no longer in the list (matched case-insensitively)
        for sender in list(db_newsletter.senders):
            sender_lower = sender.email.lower()
            if (
                sender_lower not in new_emails_lower
                or sender_lower in existing_emails_lower
            ):
                db.delete(sender)
            else:
                if sender.email != sender_lower:
                    sender.email = sender_lower
                existing_emails_lower.add(sender_lower)

        db.flush()

        # Add new senders
        for email in newsletter_update.sender_emails:
            email_lower = email.lower()
            if email_lower not in existing_emails_lower:
                db_sender = Sender(
                    id=generate(), email=email_lower, newsletter_id=db_newsletter.id
                )
                db.add(db_sender)
                existing_emails_lower.add(email_lower)

        db.commit()
        db.refresh(db_newsletter)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update newsletter: {e}", exc_info=True)
        raise

    logger.info(f"Successfully updated newsletter with id={db_newsletter.id}")
    bump_metadata_version()
    clear_identity_cache()
    return get_newsletter_by_identifier(db, newsletter_id)


def delete_newsletter(db: Session, newsletter_id: str) -> Newsletter | None:
    """Delete a newsletter by its ID."""
    logger.info(f"Deleting newsletter with id={newsletter_id}")
    db_newsletter = get_newsletter_by_identifier(db, newsletter_id)
    if not db_newsletter:
        return None

    try:
        db.delete(db_newsletter)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete newsletter: {e}", exc_info=True)
        raise

    # Invalidate caches: entries are gone (timestamp cache) and the newsletter
    # set changed (metadata version), which busts the master feed's ETag too.
    clear_latest_timestamp_cache()
    bump_metadata_version()
    clear_identity_cache()

    logger.info(f"Successfully deleted newsletter with id={newsletter_id}")
    return db_newsletter
