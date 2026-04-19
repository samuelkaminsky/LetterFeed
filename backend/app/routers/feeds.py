import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException
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
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
):
    """Generate a master Atom feed for all newsletters."""
    logger.info("Generating master feed for all newsletters")
    
    latest_timestamp = get_latest_entry_timestamp(db)
    etag = _generate_etag("master", latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    feed = generate_master_feed(db)
    logger.info("Successfully generated master feed")
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers={"ETag": etag}
    )


@router.get("/feeds/{feed_identifier}")
def get_newsletter_feed(
    feed_identifier: str, 
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
):
    """Generate an Atom feed for a specific newsletter."""
    logger.info(f"Generating feed for newsletter with identifier={feed_identifier}")
    
    newsletter = get_newsletter_by_identifier(db, feed_identifier)
    if not newsletter:
        logger.warning(
            f"Newsletter with identifier={feed_identifier} not found, cannot generate feed."
        )
        raise HTTPException(status_code=404, detail="Newsletter not found")

    latest_timestamp = get_latest_entry_timestamp(db, newsletter_id=newsletter.id)
    etag = _generate_etag(newsletter.id, latest_timestamp)
    
    if if_none_match == etag:
        logger.debug("Feed unmodified, returning 304")
        return Response(status_code=304)

    feed = generate_feed(db, feed_identifier)
    if not feed:
        raise HTTPException(status_code=404, detail="Newsletter not found")

    logger.info(
        f"Successfully generated feed for newsletter with identifier={feed_identifier}"
    )
    return Response(
        content=feed, 
        media_type="application/atom+xml",
        headers={"ETag": etag}
    )
