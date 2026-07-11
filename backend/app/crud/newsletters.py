from nanoid import generate
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.logging import get_logger
from app.crud.entries import bump_metadata_version, clear_latest_timestamp_cache
from app.models.entries import Entry
from app.models.newsletters import Newsletter, Sender
from app.schemas.newsletters import NewsletterCreate, NewsletterUpdate

logger = get_logger(__name__)


def get_newsletter_by_identifier(db: Session, identifier: str):
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


def get_newsletter_by_slug(db: Session, slug: str):
    """Retrieve a newsletter by its slug."""
    return db.query(Newsletter).filter(Newsletter.slug == slug).first()


# Cache of identifier -> (id, slug). Newsletter identity is stable between
# metadata changes, so this lets the conditional-request (304) hot path resolve
# a slug/id without touching the DB. Cleared on any newsletter create/update/
# delete (same points that bump the metadata version). Process-local; assumes a
# single worker, like the other in-memory caches.
_identity_cache: dict[str, tuple[str, str | None]] = {}


def get_newsletter_identity(db: Session, identifier: str) -> tuple[str, str | None] | None:
    """Resolve a newsletter's (id, slug) by id or slug, cached in memory.

    Lightweight alternative to get_newsletter_by_identifier for the feed hot
    path: no entry-count aggregation and no sender load.
    """
    if identifier in _identity_cache:
        return _identity_cache[identifier]

    row = (
        db.query(Newsletter.id, Newsletter.slug)
        .filter(or_(Newsletter.id == identifier, Newsletter.slug == identifier))
        .first()
    )
    if row is None:
        return None

    identity = (row.id, row.slug)
    _identity_cache[identifier] = identity
    return identity


def clear_identity_cache() -> None:
    """Invalidate the identifier -> identity cache."""
    _identity_cache.clear()


def get_newsletters(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve a list of newsletters."""
    logger.debug(f"Querying for newsletters with skip={skip}, limit={limit}")
    results = (
        db.query(Newsletter, func.count(Entry.id))
        .outerjoin(Entry, Newsletter.id == Entry.newsletter_id)
        .group_by(Newsletter.id)
        .order_by(Newsletter.id)
        .options(selectinload(Newsletter.senders))
        .offset(skip)
        .limit(limit)
        .all()
    )

    newsletters_with_count = []
    for newsletter, count in results:
        newsletter.entries_count = count
        newsletters_with_count.append(newsletter)

    return newsletters_with_count


def create_newsletter(db: Session, newsletter: NewsletterCreate):
    """Create a new newsletter."""
    logger.info(f"Creating new newsletter with name '{newsletter.name}'")

    if newsletter.slug and get_newsletter_by_slug(db, newsletter.slug):
        return None  # Indicates a conflict

    db_newsletter = Newsletter(
        id=generate(size=10),
        name=newsletter.name,
        slug=newsletter.slug,
        search_folder=newsletter.search_folder,
        extract_content=newsletter.extract_content,
        move_to_folder=newsletter.move_to_folder,
    )
    db.add(db_newsletter)
    db.commit()
    db.refresh(db_newsletter)

    for email in newsletter.sender_emails:
        db_sender = Sender(id=generate(), email=email, newsletter_id=db_newsletter.id)
        db.add(db_sender)

    db.commit()
    db.refresh(db_newsletter)

    logger.info(f"Successfully created newsletter with id={db_newsletter.id}")
    bump_metadata_version()
    clear_identity_cache()
    db_newsletter.entries_count = 0
    return db_newsletter


def update_newsletter(
    db: Session, newsletter_id: str, newsletter_update: NewsletterUpdate
):
    """Update an existing newsletter."""
    logger.info(f"Updating newsletter with id={newsletter_id}")
    db_newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
    if not db_newsletter:
        return None

    if newsletter_update.slug:
        existing_newsletter = get_newsletter_by_slug(db, newsletter_update.slug)
        if existing_newsletter and existing_newsletter.id != newsletter_id:
            return "conflict"  # Indicates a conflict

    update_data = newsletter_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "sender_emails":
            continue
        setattr(db_newsletter, key, value)

    # More efficient sender update
    existing_emails = {sender.email for sender in db_newsletter.senders}
    new_emails = set(newsletter_update.sender_emails)

    # Remove senders that are no longer in the list
    for sender in db_newsletter.senders:
        if sender.email not in new_emails:
            db.delete(sender)

    # Add new senders
    for email in new_emails:
        if email not in existing_emails:
            db_sender = Sender(
                id=generate(), email=email, newsletter_id=db_newsletter.id
            )
            db.add(db_sender)

    db.commit()
    db.refresh(db_newsletter)

    logger.info(f"Successfully updated newsletter with id={db_newsletter.id}")
    bump_metadata_version()
    clear_identity_cache()
    return get_newsletter_by_identifier(db, newsletter_id)


def delete_newsletter(db: Session, newsletter_id: str):
    """Delete a newsletter by its ID."""
    logger.info(f"Deleting newsletter with id={newsletter_id}")
    db_newsletter = get_newsletter_by_identifier(db, newsletter_id)
    if not db_newsletter:
        return None

    db.delete(db_newsletter)
    db.commit()

    # Invalidate caches: entries are gone (timestamp cache) and the newsletter
    # set changed (metadata version), which busts the master feed's ETag too.
    clear_latest_timestamp_cache()
    bump_metadata_version()
    clear_identity_cache()

    logger.info(f"Successfully deleted newsletter with id={newsletter_id}")
    return db_newsletter
