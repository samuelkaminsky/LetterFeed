import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.crud.entries import get_latest_entry_timestamp_cached
from app.crud.feed_cache import get_cached_feed, set_cached_feed
from app.crud.newsletters import get_newsletter_by_identifier
from app.services.feed_generator import generate_feed, generate_master_feed

logger = get_logger(__name__)
router = APIRouter()


def _generate_etag(identifier: str, timestamp) -> str:
    """Generate a simple ETag based on an identifier and a timestamp."""
    ts_str = str(timestamp.timestamp()) if timestamp else "empty"
    etag_raw = f"{identifier}-{ts_str}"
    return f'"{hashlib.md5(etag_raw.encode()).hexdigest()}"'


@router.get("/feeds/all")
def get_master_feed(
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
):
    """Generate a master Atom feed for all newsletters."""
    # Authenticate the master feed if auth is enabled
    import secrets

    from app.core.auth import is_auth_enabled
    from app.crud.settings import get_settings

    if is_auth_enabled(db):
        db_settings = get_settings(db)
        if not token or not db_settings.master_feed_token or not secrets.compare_digest(token, db_settings.master_feed_token):
            logger.warning("Unauthorized attempt to access master feed (invalid or missing token)")
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing token")

    logger.info("Generating master feed for all newsletters")
    
    latest_timestamp = get_latest_entry_timestamp_cached(db)
    etag = _generate_etag("master", latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    # HTTP If-Modified-Since check
    if if_modified_since and latest_timestamp:
        try:
            import datetime
            from email.utils import parsedate_to_datetime
            ims_datetime = parsedate_to_datetime(if_modified_since)
            latest_timestamp_tz = (
                latest_timestamp.replace(tzinfo=datetime.UTC)
                if latest_timestamp.tzinfo is None
                else latest_timestamp.astimezone(datetime.UTC)
            )
            if latest_timestamp_tz.replace(microsecond=0) <= ims_datetime.replace(microsecond=0):
                logger.debug("Feed unmodified since If-Modified-Since, returning 304")
                return Response(status_code=304)
        except Exception as e:
            logger.warning(f"Error parsing If-Modified-Since header: {e}")

    # Determine Last-Modified header value
    import datetime
    from email.utils import format_datetime
    last_modified_str = None
    if latest_timestamp:
        latest_timestamp_tz = (
            latest_timestamp.replace(tzinfo=datetime.UTC)
            if latest_timestamp.tzinfo is None
            else latest_timestamp.astimezone(datetime.UTC)
        )
        last_modified_str = format_datetime(latest_timestamp_tz, usegmt=True)

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=60"
    }
    if last_modified_str:
        headers["Last-Modified"] = last_modified_str

    cached_feed = get_cached_feed(db, "master", etag)
    if cached_feed is not None:
        logger.info("Returning cached master feed")
        return Response(
            content=cached_feed,
            media_type="application/atom+xml",
            headers=headers
        )

    feed = generate_master_feed(db, request=request)
    set_cached_feed(db, "master", etag, feed)
    logger.info("Successfully generated master feed")
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers=headers
    )


@router.get("/feeds/{feed_identifier}")
def get_newsletter_feed(
    feed_identifier: str, 
    request: Request,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
):
    """Generate an Atom feed for a specific newsletter."""
    # Secure feeds: Restrict RSS feeds strictly to the cryptographically secure ID (NanoID)
    # to prevent slug guessing when authentication is enabled.
    from app.core.auth import is_auth_enabled
    
    logger.info(f"Generating feed for newsletter with identifier={feed_identifier}")
    
    newsletter = get_newsletter_by_identifier(db, feed_identifier)
    if not newsletter:
        logger.warning(
            f"Newsletter with identifier={feed_identifier} not found, cannot generate feed."
        )
        raise HTTPException(status_code=404, detail="Newsletter not found")

    if is_auth_enabled(db) and newsletter.slug == feed_identifier:
        logger.warning(
            f"Blocked guessable slug-based feed access for slug '{feed_identifier}'."
        )
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Guessable slug-based feed access is disabled for security. Please use the secure feed ID."
        )

    latest_timestamp = get_latest_entry_timestamp_cached(db, newsletter_id=newsletter.id)
    etag = _generate_etag(newsletter.id, latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    # HTTP If-Modified-Since check
    if if_modified_since and latest_timestamp:
        try:
            import datetime
            from email.utils import parsedate_to_datetime
            ims_datetime = parsedate_to_datetime(if_modified_since)
            latest_timestamp_tz = (
                latest_timestamp.replace(tzinfo=datetime.UTC)
                if latest_timestamp.tzinfo is None
                else latest_timestamp.astimezone(datetime.UTC)
            )
            if latest_timestamp_tz.replace(microsecond=0) <= ims_datetime.replace(microsecond=0):
                logger.debug("Feed unmodified since If-Modified-Since, returning 304")
                return Response(status_code=304)
        except Exception as e:
            logger.warning(f"Error parsing If-Modified-Since header: {e}")

    # Determine Last-Modified header value
    import datetime
    from email.utils import format_datetime
    last_modified_str = None
    if latest_timestamp:
        latest_timestamp_tz = (
            latest_timestamp.replace(tzinfo=datetime.UTC)
            if latest_timestamp.tzinfo is None
            else latest_timestamp.astimezone(datetime.UTC)
        )
        last_modified_str = format_datetime(latest_timestamp_tz, usegmt=True)

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=60"
    }
    if last_modified_str:
        headers["Last-Modified"] = last_modified_str

    cached_feed = get_cached_feed(db, newsletter.id, etag)
    if cached_feed is not None:
        logger.info(f"Returning cached feed for newsletter_id={newsletter.id}")
        return Response(
            content=cached_feed,
            media_type="application/atom+xml",
            headers=headers
        )

    # For generate_feed, always pass the secure newsletter ID to prevent any internal slug mapping issues
    feed = generate_feed(
        db,
        newsletter.id,
        request=request,
        limit=settings.newsletter_feed_limit,
    )
    if not feed:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    set_cached_feed(db, newsletter.id, etag, feed)
    logger.info(
        f"Successfully generated feed for newsletter with identifier={feed_identifier}"
    )
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers=headers
    )
