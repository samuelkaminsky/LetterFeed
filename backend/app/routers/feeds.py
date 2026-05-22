import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.crud.entries import get_latest_entry_timestamp
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
):
    """Generate a master Atom feed for all newsletters."""
    # Authenticate the master feed if auth is enabled
    import secrets

    from app.core.auth import is_auth_enabled
    from app.crud.settings import get_settings

    if is_auth_enabled(db):
        settings = get_settings(db)
        if not token or not settings.master_feed_token or not secrets.compare_digest(token, settings.master_feed_token):
            logger.warning("Unauthorized attempt to access master feed (invalid or missing token)")
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing token")

    logger.info("Generating master feed for all newsletters")
    
    latest_timestamp = get_latest_entry_timestamp(db)
    etag = _generate_etag("master", latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    feed = generate_master_feed(db, request=request)
    logger.info("Successfully generated master feed")
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=60"
        }
    )


@router.get("/feeds/{feed_identifier}")
def get_newsletter_feed(
    feed_identifier: str, 
    request: Request,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
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

    latest_timestamp = get_latest_entry_timestamp(db, newsletter_id=newsletter.id)
    etag = _generate_etag(newsletter.id, latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    # For generate_feed, always pass the secure newsletter ID to prevent any internal slug mapping issues
    feed = generate_feed(db, newsletter.id, request=request)
    if not feed:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    logger.info(
        f"Successfully generated feed for newsletter with identifier={feed_identifier}"
    )
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=60"
        }
    )
