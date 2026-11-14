import imaplib
from email.message import Message
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.imap import get_folders
from app.crud.entries import get_entries_by_newsletter
from app.crud.newsletters import create_newsletter, get_newsletters
from app.crud.settings import create_or_update_settings
from app.models.newsletters import Newsletter
from app.schemas.newsletters import NewsletterCreate
from app.schemas.settings import Settings, SettingsCreate
from app.services.email_processor import (
    _process_single_email,
    _send_notification_email,
    process_emails,
)


def _setup_test_email_processing(
    db_session: Session,
    newsletter_create_data: NewsletterCreate,
    settings_create_data: SettingsCreate,
) -> tuple[MagicMock, Newsletter, Settings]:
    """Help to set up mocks and data for email processing tests."""
    settings = create_or_update_settings(db_session, settings_create_data)
    newsletter = create_newsletter(db_session, newsletter_create_data)

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    msg = Message()
    msg["From"] = newsletter_create_data.sender_emails[0]
    msg["Subject"] = "Test Email"
    msg["Message-ID"] = "<test-message-id>"
    msg.set_payload("<html><body><p>Original Body</p></body></html>", "utf-8")
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])
    mock_mail.copy.return_value = ("OK", [b"[COPYUID ...]"])

    return mock_mail, newsletter, settings


def test_process_single_email_with_newsletter_move_folder(db_session: Session):
    """Test that the per-newsletter move_to_folder is used, overriding the global setting."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        move_to_folder="GlobalArchive",
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        move_to_folder="NewsletterArchive",
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    mock_mail.copy.assert_called_once_with("1", '"NewsletterArchive"')
    mock_mail.store.assert_any_call("1", "+FLAGS", "\\Deleted")


def test_process_single_email_with_global_move_folder(db_session: Session):
    """Test that the global move_to_folder is used when the per-newsletter one is not set."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        move_to_folder="GlobalArchive",
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter", sender_emails=["test@example.com"]
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    mock_mail.copy.assert_called_once_with("1", '"GlobalArchive"')
    mock_mail.store.assert_any_call("1", "+FLAGS", "\\Deleted")


def test_process_single_email_not_deleted_when_copy_fails(db_session: Session):
    """A failed COPY must not flag the email for deletion (avoids data loss)."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        move_to_folder="GlobalArchive",
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter", sender_emails=["test@example.com"]
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    # Simulate the destination folder not existing / copy being rejected.
    mock_mail.copy.return_value = ("NO", [b"[TRYCREATE] Mailbox does not exist"])
    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    mock_mail.copy.assert_called_once_with("1", '"GlobalArchive"')
    # The email must NOT be flagged for deletion when the copy did not succeed.
    delete_calls = [
        c
        for c in mock_mail.store.call_args_list
        if c.args[1:] == ("+FLAGS", "\\Deleted")
    ]
    assert delete_calls == []


@patch("app.services.email_processor._connect_to_imap")
def test_process_emails_uses_newsletter_search_folder(
    mock_connect_to_imap,
    db_session: Session,
):
    """Test that the per-newsletter search_folder is used, overriding the global setting."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        search_folder="GlobalInbox",
    )
    create_or_update_settings(db_session, settings_data)

    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        search_folder="NewsletterInbox",
    )
    create_newsletter(db_session, newsletter_data)

    # Mock the return of _connect_to_imap to avoid a real IMAP connection
    mock_connect_to_imap.return_value = None

    # 2. ACT
    process_emails(db_session)

    # 3. ASSERT
    # Check that _connect_to_imap was called with the newsletter's specific folder
    mock_connect_to_imap.assert_called_once()
    call_args = mock_connect_to_imap.call_args[0]
    assert call_args[1] == "NewsletterInbox"


@patch("app.services.email_processor._connect_to_imap")
def test_process_emails_uses_global_search_folder(
    mock_connect_to_imap,
    db_session: Session,
):
    """Test that the global search_folder is used when the per-newsletter one is not set."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        search_folder="GlobalInbox",
    )
    create_or_update_settings(db_session, settings_data)

    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        search_folder=None,  # Explicitly not set
    )
    create_newsletter(db_session, newsletter_data)

    mock_connect_to_imap.return_value = None

    # 2. ACT
    process_emails(db_session)

    # 3. ASSERT
    mock_connect_to_imap.assert_called_once()
    call_args = mock_connect_to_imap.call_args[0]
    assert call_args[1] == "GlobalInbox"


@patch("app.services.email_processor._extract_and_clean_html")
def test_process_single_email_with_content_extraction(
    mock_extract_clean,
    db_session: Session,
):
    """Test that the cleaning function is called when extract_content is True."""
    # 1. ARRANGE
    mock_extract_clean.return_value = {
        "title": "Extracted Title",
        "body": "Extracted Body",
    }
    settings_data = SettingsCreate(
        imap_server="test.com", imap_username="test", imap_password="password"
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        extract_content=True,
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    with patch("app.services.email_processor.create_entry") as mock_create_entry:
        _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    mock_extract_clean.assert_called_once()
    # Check that create_entry was called with the extracted body
    mock_create_entry.assert_called_once()
    entry_create_arg = mock_create_entry.call_args[0][1]
    assert entry_create_arg.body == "Extracted Body"
    # Subject should still come from the email, not the extracted title
    assert entry_create_arg.subject == "Test Email"


def test_process_single_email_sanitizes_body_without_extraction(db_session: Session):
    """Raw email HTML must be sanitized even when extract_content is disabled."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com", imap_username="test", imap_password="password"
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        extract_content=False,  # default: no readability extraction
    )
    settings = create_or_update_settings(db_session, settings_data)
    newsletter = create_newsletter(db_session, newsletter_data)

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    msg = Message()
    msg["From"] = "test@example.com"
    msg["Subject"] = "Malicious Email"
    msg["Message-ID"] = "<test-message-id-xss>"
    malicious = (
        "<p>Hello</p>"
        "<script>alert(1)</script>"
        '<img src=x onerror="alert(2)">'
        '<a href="javascript:alert(3)">click</a>'
    )
    msg.set_payload(malicious, "utf-8")
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])

    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    with patch("app.services.email_processor.create_entry") as mock_create_entry:
        _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    mock_create_entry.assert_called_once()
    stored_body = mock_create_entry.call_args[0][1].body
    assert "<script>" not in stored_body
    assert "onerror" not in stored_body
    assert "javascript:" not in stored_body
    assert "Hello" in stored_body


def test_process_single_email_with_encoded_from_header(db_session: Session):
    """Test that an encoded From header is correctly decoded for the newsletter name."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auto_add_new_senders=True,
    )
    settings = create_or_update_settings(db_session, settings_data)

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    msg = Message()
    # "Кирилл" in Cyrillic, base64 encoded for UTF-8
    from_header = "=?utf-8?B?0JrQuNGA0LjQu9C7?= <test@example.com>"
    msg["From"] = from_header
    msg["Subject"] = "Test Email"
    msg["Message-ID"] = "<test-message-id-encoded-from>"
    msg.set_payload("<html><body><p>Body</p></body></html>", "utf-8")
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])

    sender_map = {}  # empty, to trigger auto-add

    # 2. ACT
    _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    from app.crud.newsletters import get_newsletters

    newsletters = get_newsletters(db_session)
    assert len(newsletters) == 1
    assert newsletters[0].name == "Кирилл"
    assert newsletters[0].senders[0].email == "test@example.com"


def test_process_single_email_with_null_bytes_in_body(db_session: Session):
    """Test that an email with NULL bytes in its body is handled gracefully.

    - The NULL bytes should be stripped.
    - Content extraction should still be attempted.
    - If it fails, an error is logged and the raw body is used.
    """
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com", imap_username="test", imap_password="password"
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        extract_content=True,  # Important: we want to test the extraction path
    )
    settings = create_or_update_settings(db_session, settings_data)
    newsletter = create_newsletter(db_session, newsletter_data)

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    msg = Message()
    msg["From"] = "test@example.com"
    msg["Subject"] = "Test Email with NULLs"
    msg["Message-ID"] = "<test-message-id-nulls>"
    # The body contains NULL bytes that would cause readability-lxml to crash
    body_with_nulls = "<html><body><p>Hello\x00 World</p></body></html>"
    msg.set_payload(body_with_nulls, "utf-8")
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])

    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT & ASSERT
    with (
        patch("app.services.email_processor.logger") as mock_logger,
        patch("app.services.email_processor.create_entry") as mock_create_entry,
    ):
        # We mock readability.Document to simulate a failure *after* our sanitization
        # to ensure the try/except block is also working.
        with patch("app.services.email_processor.Document") as mock_document:
            mock_document.side_effect = ValueError("Simulated lxml failure")
            _process_single_email("1", mock_mail, db_session, sender_map, settings)

            # Assert that the warning was logged
            any_warning_call = any(
                "Failed to extract content" in call_args[0][0]
                for call_args in mock_logger.warning.call_args_list
            )
            assert any_warning_call, (
                "Expected a warning log containing 'Failed to extract content'"
            )

        # Check that an entry was still created
        mock_create_entry.assert_called_once()
        entry_create_arg = mock_create_entry.call_args[0][1]

        # Extraction failed, so we fall back to the SANITIZED raw body: the NULL
        # byte and unsafe wrapper tags are stripped, but the text survives.
        assert "\x00" not in entry_create_arg.body
        assert "Hello World" in entry_create_arg.body


def test_process_single_email_already_processed_still_archived(db_session: Session):
    """Test that a previously processed email is still marked as read and archived."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        move_to_folder="GlobalArchive",
        mark_as_read=True,
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    sender_map = {newsletter.senders[0].email: newsletter}

    # Pre-create entry in DB to simulate "already processed"
    from app.crud.entries import create_entry
    from app.schemas.entries import EntryCreate

    entry_schema = EntryCreate(
        subject="Test Email",
        body="Already Processed Body",
        message_id="<test-message-id>",  # matches mock msg in _setup_test_email_processing
    )
    create_entry(db_session, entry_schema, newsletter.id)

    # 2. ACT
    with patch("app.services.email_processor.create_entry") as mock_create_entry:
        _process_single_email("1", mock_mail, db_session, sender_map, settings)

    # 3. ASSERT
    # Should skip DB entry creation
    mock_create_entry.assert_not_called()
    # But should still mark as read and archive/move
    mock_mail.store.assert_any_call("1", "+FLAGS", "\\Seen")
    mock_mail.copy.assert_called_once_with("1", '"GlobalArchive"')
    mock_mail.store.assert_any_call("1", "+FLAGS", "\\Deleted")


def test_find_archive_folder():
    """Test that _find_archive_folder correctly auto-detects Archive folders."""
    from app.services.email_processor import _find_archive_folder

    # Scenario A: Special-use \Archive attribute is present
    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_mail.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\Archive) "/" "ServerArchive"',
            b'(\\HasNoChildren) "/" "Trash"',
        ],
    )
    assert _find_archive_folder(mock_mail) == "ServerArchive"

    # Scenario B: Name fallback to "Archive" (case-insensitive exact match)
    mock_mail.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Archive"',
        ],
    )
    assert _find_archive_folder(mock_mail) == "Archive"

    # Scenario C: Name fallback to "archived" (case-insensitive candidate)
    mock_mail.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren) "/" "archived"',
        ],
    )
    assert _find_archive_folder(mock_mail) == "archived"

    # Scenario D: Prioritize "archived" candidate over "All Mail"
    mock_mail.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren) "/" "All Mail"',
            b'(\\HasNoChildren) "/" "archived"',
        ],
    )
    assert _find_archive_folder(mock_mail) == "archived"


def test_process_single_email_with_auto_detected_archive_fallback(db_session: Session):
    """Test that fallback detected_archive is used when no folder is explicitly set."""
    # 1. ARRANGE
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        move_to_folder=None,  # No global archive
    )
    newsletter_data = NewsletterCreate(
        name="Test Newsletter",
        sender_emails=["test@example.com"],
        move_to_folder=None,  # No newsletter archive
    )
    mock_mail, newsletter, settings = _setup_test_email_processing(
        db_session, newsletter_data, settings_data
    )
    sender_map = {newsletter.senders[0].email: newsletter}

    # 2. ACT
    _process_single_email(
        "1",
        mock_mail,
        db_session,
        sender_map,
        settings,
        detected_archive="DetectedArchive",
    )

    # 3. ASSERT
    # Should use the detected_archive fallback
    mock_mail.copy.assert_called_once_with("1", '"DetectedArchive"')
    mock_mail.store.assert_any_call("1", "+FLAGS", "\\Deleted")


def test_process_single_email_malformed_date_and_missing_subject(db_session: Session):
    """Malformed Date and missing Subject headers should not raise exceptions."""
    settings = create_or_update_settings(
        db_session,
        SettingsCreate(
            imap_server="imap.test.com",
            imap_username="test",
            imap_password="password",
            move_to_folder=None,
        ),
    )
    newsletter = create_newsletter(
        db_session,
        NewsletterCreate(name="Fallback Header NL", sender_emails=["hdr@example.com"]),
    )

    msg = Message()
    msg["From"] = "hdr@example.com"
    msg["Message-ID"] = "<malformed-date-missing-subject>"
    msg["Date"] = "not-a-valid-rfc2822-date"
    # Intentionally omit msg["Subject"]
    msg.set_payload("<html><body><p>Body</p></body></html>", "utf-8")

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])

    deleted = _process_single_email(
        "1",
        mock_mail,
        db_session,
        {"hdr@example.com": [newsletter]},
        settings,
    )
    assert deleted is False
    entries = get_entries_by_newsletter(db_session, newsletter.id)
    assert len(entries) == 1
    assert entries[0].subject == "(No Subject)"
    assert entries[0].received_at is not None


def test_process_emails_skips_inactive_newsletter_and_does_not_revive(
    db_session: Session,
):
    """Inactive newsletters are skipped even when auto_add_new_senders is enabled."""
    create_or_update_settings(
        db_session,
        SettingsCreate(
            imap_server="imap.test.com",
            imap_username="test",
            imap_password="password",
            auto_add_new_senders=True,
            move_to_folder="Archive",
        ),
    )
    inactive_nl = create_newsletter(
        db_session,
        NewsletterCreate(
            name="Paused NL",
            sender_emails=["paused@example.com"],
            is_active=False,
        ),
    )

    msg = Message()
    msg["From"] = "paused@example.com"
    msg["Subject"] = "Should Be Skipped"
    msg["Message-ID"] = "<paused-msg-1>"
    msg.set_payload("<html><body><p>Ignored</p></body></html>", "utf-8")

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_mail.select.return_value = ("OK", [b"1"])
    mock_mail.search.return_value = ("OK", [b"1"])
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])

    with patch(
        "app.services.email_processor.imaplib.IMAP4_SSL", return_value=mock_mail
    ):
        process_emails(db_session)

    assert len(get_newsletters(db_session)) == 1
    assert get_entries_by_newsletter(db_session, inactive_nl.id) == []
    mock_mail.expunge.assert_not_called()


def test_process_emails_empty_folder_auto_add_detects_archive_and_expunges(
    db_session: Session,
):
    """Auto-add with no existing newsletters detects Archive and calls expunge iff Deleted."""
    create_or_update_settings(
        db_session,
        SettingsCreate(
            imap_server="imap.test.com",
            imap_username="test",
            imap_password="password",
            auto_add_new_senders=True,
            move_to_folder=None,
        ),
    )

    msg = Message()
    msg["From"] = "Auto NL <auto@example.com>"
    msg["Subject"] = "Hello Auto"
    msg["Message-ID"] = "<auto-msg-1>"
    msg.set_payload("<html><body><p>Content</p></body></html>", "utf-8")

    mock_mail = MagicMock(spec=imaplib.IMAP4_SSL)
    mock_mail.select.return_value = ("OK", [b"1"])
    mock_mail.list.return_value = (
        "OK",
        [b'(\\HasNoChildren \\Archive) "/" "Archive"'],
    )
    mock_mail.search.return_value = ("OK", [b"1"])
    mock_mail.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])
    mock_mail.copy.return_value = ("OK", [b"[COPYUID 1 1 1]"])

    with patch(
        "app.services.email_processor.imaplib.IMAP4_SSL", return_value=mock_mail
    ):
        process_emails(db_session)

    mock_mail.list.assert_called_once()
    mock_mail.copy.assert_called_once_with(b"1", '"Archive"')
    mock_mail.store.assert_any_call(b"1", "+FLAGS", "\\Deleted")
    mock_mail.expunge.assert_called_once()

    # Second run with no unseen emails does not call expunge
    mock_mail.expunge.reset_mock()
    mock_mail.search.return_value = ("OK", [b""])
    with patch(
        "app.services.email_processor.imaplib.IMAP4_SSL", return_value=mock_mail
    ):
        process_emails(db_session)

    mock_mail.expunge.assert_not_called()


def test_send_notification_email_from_fallback_and_empty_guard():
    """Notification email falls back to imap_username and skips if no From exists."""
    with (
        patch("app.services.email_processor.env_settings") as mock_env,
        patch("app.services.email_processor.smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_env.smtp_server = "smtp.example.com"
        mock_env.smtp_port = 587
        mock_env.notification_email_to = "dest@example.com"
        mock_env.smtp_username = ""
        mock_env.smtp_password = ""
        mock_env.imap_username = ""

        # Empty guard: neither smtp_username nor imap_username set
        _send_notification_email("Test NL", "news@example.com", "http://feed/1")
        mock_smtp_cls.assert_not_called()

        # Fallback to passed imap_username
        _send_notification_email(
            "Test NL",
            "news@example.com",
            "http://feed/1",
            imap_username="imap@example.com",
        )
        mock_smtp = mock_smtp_cls.return_value.__enter__.return_value
        mock_smtp.send_message.assert_called_once()
        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert sent_msg["From"] == "imap@example.com"


def test_get_folders_short_circuits_on_empty_credentials():
    """get_folders returns [] without opening an IMAP socket when creds are missing."""
    with patch("app.core.imap.imaplib.IMAP4_SSL") as mock_imap:
        assert get_folders("", "user", "pass") == []
        assert get_folders("imap.example.com", "", "pass") == []
        assert get_folders("imap.example.com", "user", "") == []
        mock_imap.assert_not_called()


def test_imap_process_endpoint_returns_generic_500_on_unexpected_error(
    client: TestClient,
):
    """POST /imap/process hides exception details on unexpected 500 errors."""
    with patch(
        "app.routers.imap.process_emails",
        side_effect=RuntimeError("sensitive-credential-leak"),
    ):
        response = client.post("/imap/process")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error during email processing."
    assert "sensitive-credential-leak" not in response.text
