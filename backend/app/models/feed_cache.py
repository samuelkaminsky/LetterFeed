import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base


class FeedCache(Base):
    """Represents a cached RSS/Atom feed generated for a newsletter or the master feed."""

    __tablename__ = "feed_caches"

    feed_id = Column(String, primary_key=True, index=True)
    etag = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
