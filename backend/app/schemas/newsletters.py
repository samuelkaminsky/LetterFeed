from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, field_validator

from app.core.slug import sanitize_slug


def _normalize_sender_emails(emails: list[EmailStr]) -> list[EmailStr]:
    """Lowercase and deduplicate sender email addresses while preserving order."""
    seen: set[str] = set()
    normalized: list[EmailStr] = []
    for raw_email in emails:
        lowered = str(raw_email).strip().lower()
        if lowered not in seen:
            seen.add(lowered)
            normalized.append(lowered)
    return normalized


NormalizedSenderEmails = Annotated[
    list[EmailStr], AfterValidator(_normalize_sender_emails)
]


class SenderBase(BaseModel):
    """Base schema for a sender."""

    email: EmailStr


class Sender(SenderBase):
    """Schema for retrieving a sender with its ID and newsletter ID."""

    id: str
    newsletter_id: str

    model_config = ConfigDict(from_attributes=True)


class NewsletterBase(BaseModel):
    """Base schema for a newsletter."""

    name: str
    slug: str | None = None
    search_folder: str | None = None
    move_to_folder: str | None = None
    is_active: bool = True
    extract_content: bool = False

    @field_validator("slug")
    @classmethod
    def sanitize_slug_field(cls, v: str | None) -> str | None:
        """Sanitize slug and reject reserved identifiers."""
        sanitized = sanitize_slug(v)
        if sanitized == "all":
            raise ValueError("Slug 'all' is reserved")
        return sanitized


class NewsletterCreate(NewsletterBase):
    """Schema for creating a new newsletter."""

    sender_emails: NormalizedSenderEmails


class NewsletterUpdate(NewsletterBase):
    """Schema for updating an existing newsletter."""

    sender_emails: NormalizedSenderEmails


class Newsletter(NewsletterBase):
    """Schema for retrieving a newsletter with its ID, active status, senders, and entries count."""

    id: str
    senders: list[Sender] = []
    entries_count: int

    model_config = ConfigDict(from_attributes=True)
