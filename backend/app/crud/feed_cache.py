from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.feed_cache import FeedCache

logger = get_logger(__name__)

# In-memory cache for feeds: feed_id -> (etag, content_str)
_feed_memory_cache = {}


def get_cached_feed(db: Session, feed_id: str, current_etag: str) -> str | None:
    """Retrieve cached feed content if the etag matches current_etag."""
    logger.debug(f"Checking cache for feed_id={feed_id} with current_etag={current_etag}")
    
    # Check in-memory cache first
    if feed_id in _feed_memory_cache:
        cached_etag, cached_content = _feed_memory_cache[feed_id]
        if cached_etag == current_etag:
            logger.debug(f"Memory cache hit for feed_id={feed_id} with etag={current_etag}")
            return cached_content

    # Fall back to DB cache
    cache_entry = db.query(FeedCache).filter(FeedCache.feed_id == feed_id).first()
    if cache_entry and cache_entry.etag == current_etag:
        logger.debug(f"DB Cache hit for feed_id={feed_id} with etag={current_etag}. Updating memory cache.")
        _feed_memory_cache[feed_id] = (current_etag, cache_entry.content)
        return cache_entry.content
        
    logger.debug(f"Cache miss for feed_id={feed_id}")
    return None


def set_cached_feed(db: Session, feed_id: str, etag: str, content: bytes | str) -> None:
    """Insert or update (upsert) feed content and etag in the cache."""
    logger.info(f"Caching feed_id={feed_id} with etag={etag}")
    content_str = content.decode("utf-8") if isinstance(content, bytes) else content
    
    # Update memory cache
    _feed_memory_cache[feed_id] = (etag, content_str)
    
    # Update DB cache
    cache_entry = db.query(FeedCache).filter(FeedCache.feed_id == feed_id).first()
    if cache_entry:
        cache_entry.etag = etag
        cache_entry.content = content_str
        cache_entry.generated_at = datetime.now()
    else:
        cache_entry = FeedCache(
            feed_id=feed_id,
            etag=etag,
            content=content_str,
            generated_at=datetime.now(),
        )
        db.add(cache_entry)
    db.commit()


def delete_cached_feed(db: Session, feed_id: str) -> None:
    """Delete cached feed content for a feed_id."""
    logger.info(f"Invalidating cache for feed_id={feed_id}")
    _feed_memory_cache.pop(feed_id, None)
    db.query(FeedCache).filter(FeedCache.feed_id == feed_id).delete()
    db.commit()
