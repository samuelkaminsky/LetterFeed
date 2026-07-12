from typing import List

from pydantic import BaseModel, ConfigDict, Field


class SettingsBase(BaseModel):
    """Base schema for application settings."""

    imap_server: str
    imap_username: str
    search_folder: str = "INBOX"
    move_to_folder: str | None = None
    mark_as_read: bool = False
    email_check_interval: int = 15
    auto_add_new_senders: bool = False
    auth_username: str | None = None


class SettingsCreate(SettingsBase):
    """Schema for creating or updating settings, including the IMAP password."""

    imap_password: str | None = None
    auth_password: str | None = None
    # Must be >= 1: a 0/negative interval makes APScheduler raise and would leave
    # the email-check job unscheduled (no email processing).
    email_check_interval: int = Field(default=15, ge=1)


class Settings(SettingsBase):
    """Schema for retrieving settings, with password excluded by default."""

    id: int
    imap_password: str | None = Field(None, exclude=True)
    auth_password: str | None = Field(None, exclude=True)
    master_feed_token: str | None = None
    locked_fields: List[str] = []

    model_config = ConfigDict(from_attributes=True)
