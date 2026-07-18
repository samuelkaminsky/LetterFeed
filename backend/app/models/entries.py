from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Entry(Base):
    """Represents an entry (e.g., an email) associated with a newsletter."""

    __tablename__ = "entries"

    id = Column(String, primary_key=True, index=True)
    newsletter_id = Column(String, ForeignKey("newsletters.id"))
    subject = Column(String)
    body = Column(Text)
    received_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    message_id = Column(String, index=True, nullable=False)

    newsletter = relationship("Newsletter", back_populates="entries")

    __table_args__ = (
        UniqueConstraint(
            "message_id", "newsletter_id", name="uq_entry_message_newsletter"
        ),
        Index("ix_entries_newsletter_id_received_at", "newsletter_id", "received_at"),
    )
