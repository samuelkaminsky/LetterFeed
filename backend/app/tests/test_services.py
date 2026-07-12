import uuid
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

from fastapi import Request
from sqlalchemy.orm import Session

from app.crud.entries import create_entry
from app.crud.newsletters import create_newsletter
from app.schemas.entries import EntryCreate
from app.schemas.newsletters import NewsletterCreate
from app.services.feed_generator import generate_feed, generate_master_feed


def test_generate_master_feed(db_session: Session):
    """Test the master feed generation for all newsletters."""
    # Create newsletters and entries
    nl1 = create_newsletter(
        db_session,
        NewsletterCreate(name="Newsletter A", sender_emails=["a@example.com"]),
    )
    create_entry(
        db_session,
        EntryCreate(
            subject="Entry A1", body="<p>Body A1</p>", message_id=f"<{uuid.uuid4()}>"
        ),
        nl1.id,
    )

    nl2 = create_newsletter(
        db_session,
        NewsletterCreate(name="Newsletter B", sender_emails=["b@example.com"]),
    )
    create_entry(
        db_session,
        EntryCreate(
            subject="Entry B1", body="<p>Body B1</p>", message_id=f"<{uuid.uuid4()}>"
        ),
        nl2.id,
    )

    # Generate the master feed
    feed_xml = generate_master_feed(db_session)
    assert feed_xml is not None

    # Parse and verify
    root = ET.fromstring(feed_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    assert root.find("atom:title", ns).text == "LetterFeed: All Newsletters"
    assert root.find("atom:id", ns).text == "urn:letterfeed:master"

    entry_titles = {
        entry.find("atom:title", ns).text for entry in root.findall("atom:entry", ns)
    }
    assert "[Newsletter A] Entry A1" in entry_titles
    assert "[Newsletter B] Entry B1" in entry_titles


def test_generate_feed(db_session: Session):
    """Test the feed generation for a newsletter with entries."""
    # Create a newsletter
    newsletter_data = NewsletterCreate(
        name="Feed Test Newsletter", sender_emails=["feed@example.com"]
    )
    newsletter = create_newsletter(db_session, newsletter_data)

    # Create entries for the newsletter
    entry1_data = EntryCreate(
        subject="First Entry",
        body="<p>This is the first entry.</p>",
        message_id=f"<{uuid.uuid4()}@test.com>",
    )
    create_entry(db_session, entry1_data, newsletter.id)

    entry2_data = EntryCreate(
        subject="Second Entry",
        body="<p>This is the second entry.</p>",
        message_id=f"<{uuid.uuid4()}@test.com>",
    )
    create_entry(db_session, entry2_data, newsletter.id)

    # Generate the feed
    feed_xml = generate_feed(db_session, newsletter.id)
    assert feed_xml is not None

    # Parse the feed XML to verify content
    root = ET.fromstring(feed_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Check for top-level elements
    assert root.find("atom:title", ns).text == newsletter.name
    assert root.find("atom:id", ns).text == f"urn:letterfeed:newsletter:{newsletter.id}"
    assert root.find("atom:logo", ns).text.endswith("/logo.png")
    assert root.find("atom:icon", ns).text.endswith("/favicon.ico")

    # Check for the alternate link
    links = root.findall("atom:link", ns)
    assert any(link.get("rel") == "alternate" and link.get("href") for link in links)

    # Check for entries
    entry_titles = [
        entry.find("atom:title", ns).text for entry in root.findall("atom:entry", ns)
    ]
    assert "First Entry" in entry_titles
    assert "Second Entry" in entry_titles

    # Check content of one entry
    first_entry_element = root.find(".//atom:title[.='First Entry']/..", ns)
    assert (
        first_entry_element.find("atom:content", ns).text
        == "<p>This is the first entry.</p>"
    )


def test_generate_feed_nonexistent_newsletter(db_session: Session):
    """Test feed generation for a non-existent newsletter."""
    feed_xml = generate_feed(db_session, "nonexistent-id")
    assert feed_xml is None


def test_generate_feed_with_proxy_request(db_session: Session):
    """Test that feed generation dynamically uses reverse proxy headers for self-links."""
    # Create a newsletter
    newsletter_data = NewsletterCreate(
        name="Proxy Test", sender_emails=["proxy@example.com"]
    )
    newsletter = create_newsletter(db_session, newsletter_data)
    
    # Create a mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {
        "x-forwarded-host": "letterfeed.example.com",
        "x-forwarded-proto": "https"
    }

    # The forwarded host is only reflected when it is a configured/trusted host.
    with patch(
        "app.services.feed_generator._trusted_hosts",
        return_value={"letterfeed.example.com"},
    ):
        feed_xml = generate_feed(db_session, newsletter.id, request=mock_request)
    assert feed_xml is not None

    # Parse the feed XML to verify content
    root = ET.fromstring(feed_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Check for the self link
    links = root.findall("atom:link", ns)
    self_link = next(link for link in links if link.get("rel") == "self")
    assert self_link.get("href") == f"https://letterfeed.example.com/api/feeds/{newsletter.id}"
    
    # Check alternate link, logo, and icon
    alternate_link = next(link for link in links if link.get("rel") == "alternate")
    assert alternate_link.get("href") == "https://letterfeed.example.com/"
    assert root.find("atom:logo", ns).text == "https://letterfeed.example.com/logo.png"
    assert root.find("atom:icon", ns).text == "https://letterfeed.example.com/favicon.ico"


def test_generate_master_feed_with_proxy_request(db_session: Session):
    """Test that master feed generation dynamically uses reverse proxy headers for self-links."""
    # Create a mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {
        "x-forwarded-host": "letterfeed.example.com",
        "x-forwarded-proto": "https"
    }

    # The forwarded host is only reflected when it is a configured/trusted host.
    with patch(
        "app.services.feed_generator._trusted_hosts",
        return_value={"letterfeed.example.com"},
    ):
        feed_xml = generate_master_feed(db_session, request=mock_request)
    assert feed_xml is not None

    # Parse the feed XML to verify content
    root = ET.fromstring(feed_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Check for the self link
    links = root.findall("atom:link", ns)
    self_link = next(link for link in links if link.get("rel") == "self")
    assert self_link.get("href") == "https://letterfeed.example.com/api/feeds/all"


def test_generate_feed_ignores_untrusted_forwarded_host(db_session: Session):
    """An attacker-supplied X-Forwarded-Host must not be reflected into feed links."""
    newsletter = create_newsletter(
        db_session,
        NewsletterCreate(name="Poison Test", sender_emails=["poison@example.com"]),
    )

    mock_request = MagicMock(spec=Request)
    mock_request.url.scheme = "http"
    mock_request.headers = {
        "x-forwarded-host": "evil.example.net",
        "x-forwarded-proto": "https",
        "host": "evil.example.net",
    }

    # No trusted hosts configured -> the spoofed header is ignored and generation
    # falls back to the configured app_base_url instead of the attacker's host.
    with patch("app.services.feed_generator._trusted_hosts", return_value=set()):
        feed_xml = generate_feed(db_session, newsletter.id, request=mock_request)
    assert feed_xml is not None
    assert b"evil.example.net" not in feed_xml
