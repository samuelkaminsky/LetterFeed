import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.feed_cache import FeedCache


def test_feed_caching_and_invalidation(client: TestClient, db_session: Session):
    """Test that a feed is cached and the cache is served on subsequent requests."""
    # 1. Create newsletter
    unique_email = f"cache_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Cache Test Newsletter", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    # 2. Add an entry to the newsletter
    entry_data = {
        "subject": "Test Entry 1",
        "body": "<p>Content 1</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # 3. Request the feed (should generate and cache it)
    response_1 = client.get(f"/feeds/{newsletter_id}")
    assert response_1.status_code == 200
    assert "Test Entry 1" in response_1.text

    # 4. Check that cache entry exists in db
    cache_record = db_session.query(FeedCache).filter(FeedCache.feed_id == newsletter_id).first()
    assert cache_record is not None
    assert cache_record.etag is not None
    assert "Test Entry 1" in cache_record.content

    # 5. Mutate the cached feed content directly in the database to verify it is served
    original_etag = cache_record.etag
    fake_content = "<feed><title>Cached Feed Fake</title></feed>"
    cache_record.content = fake_content
    db_session.commit()

    # Clear memory cache since we bypassed the CRUD set function
    from app.crud.feed_cache import _feed_memory_cache
    _feed_memory_cache.clear()

    # 6. Fetch again: should return our modified cached content (cache hit)
    response_2 = client.get(f"/feeds/{newsletter_id}")
    assert response_2.status_code == 200
    assert response_2.text == fake_content

    # 7. Add a second entry (should invalidate ETag and cause a cache miss)
    entry_data_2 = {
        "subject": "Test Entry 2",
        "body": "<p>Content 2</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data_2)

    # 8. Fetch again: should regenerate feed with both entries and update the cache
    response_3 = client.get(f"/feeds/{newsletter_id}")
    assert response_3.status_code == 200
    assert "Test Entry 1" in response_3.text
    assert "Test Entry 2" in response_3.text
    assert "Cached Feed Fake" not in response_3.text

    # 9. Verify the database now has a different ETag and updated content
    db_session.refresh(cache_record)
    assert cache_record.etag != original_etag
    assert "Test Entry 2" in cache_record.content


def test_master_feed_caching(client: TestClient, db_session: Session):
    """Test caching behavior for the master feed endpoint."""
    unique_email = f"master_cache_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Master Cache NL", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    entry_data = {
        "subject": "Master Test Entry",
        "body": "<p>Master Content</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # Fetch master feed
    res_1 = client.get("/feeds/all")
    assert res_1.status_code == 200
    assert "Master Test Entry" in res_1.text

    # Verify cache record exists
    cache_record = db_session.query(FeedCache).filter(FeedCache.feed_id == "master").first()
    assert cache_record is not None

    # Mutate the cache record
    fake_master_content = "<feed><title>Cached Master Fake</title></feed>"
    cache_record.content = fake_master_content
    db_session.commit()

    # Clear memory cache since we bypassed the CRUD set function
    from app.crud.feed_cache import _feed_memory_cache
    _feed_memory_cache.clear()

    # Fetch master feed again: should hit the cache and return the mutated content
    res_2 = client.get("/feeds/all")
    assert res_2.status_code == 200
    assert res_2.text == fake_master_content


def test_newsletter_feed_limit(client: TestClient, db_session: Session):
    """Test that individual feeds respect the newsletter_feed_limit."""
    unique_email = f"limit_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Limit Test Newsletter", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    # Add 3 entries
    for i in range(1, 4):
        entry_data = {
            "subject": f"Entry {i}",
            "body": f"<p>Content {i}</p>",
            "message_id": f"<entry_{i}_{uuid.uuid4()}@test.com>",
        }
        client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # Request the feed and verify we get all 3 by default
    res_default = client.get(f"/feeds/{newsletter_id}")
    assert res_default.status_code == 200
    assert "Entry 1" in res_default.text
    assert "Entry 2" in res_default.text
    assert "Entry 3" in res_default.text

    # Now patch settings.newsletter_feed_limit to 2
    # Ensure cache is invalidated by mutating etag or querying directly with patch
    with patch("app.routers.feeds.settings") as mock_settings:
        mock_settings.newsletter_feed_limit = 2
        mock_settings.app_base_url = "http://backend:8000"
        
        # Clear the cache first to force regeneration
        db_session.query(FeedCache).filter(FeedCache.feed_id == newsletter_id).delete()
        db_session.commit()

        # Clear memory cache since we bypassed the CRUD delete function
        from app.crud.feed_cache import _feed_memory_cache
        _feed_memory_cache.clear()

        res_limited = client.get(f"/feeds/{newsletter_id}")
        assert res_limited.status_code == 200
        
        import xml.etree.ElementTree as ET
        root = ET.fromstring(res_limited.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        
        # Should be limited to 2 entries
        assert len(entries) == 2
        
        entry_titles = [entry.find("atom:title", ns).text for entry in entries]
        # Should be the latest 2 entries (Entry 3 and Entry 2)
        assert "Entry 3" in entry_titles
        assert "Entry 2" in entry_titles
        assert "Entry 1" not in entry_titles


def test_feed_refreshes_when_newsletter_renamed(client: TestClient, db_session: Session):
    """Renaming a newsletter must change the ETag and regenerate the feed.

    A rename does not advance the latest-entry timestamp, so without folding the
    metadata version into the ETag the cached feed (and 304s) would keep serving
    the old name indefinitely.
    """
    unique_email = f"rename_{uuid.uuid4()}@example.com"
    create_response = client.post(
        "/newsletters",
        json={"name": "Original Name", "sender_emails": [unique_email]},
    )
    newsletter_id = create_response.json()["id"]

    client.post(
        f"/newsletters/{newsletter_id}/entries",
        json={
            "subject": "Entry",
            "body": "<p>Content</p>",
            "message_id": f"<entry_{uuid.uuid4()}@test.com>",
        },
    )

    res_1 = client.get(f"/feeds/{newsletter_id}")
    assert res_1.status_code == 200
    assert "Original Name" in res_1.text
    etag_1 = res_1.headers.get("ETag")

    # Rename the newsletter (senders unchanged).
    client.put(
        f"/newsletters/{newsletter_id}",
        json={"name": "New Name", "sender_emails": [unique_email], "extract_content": False},
    )

    # A conditional request with the old ETag must NOT get a 304.
    res_stale = client.get(
        f"/feeds/{newsletter_id}", headers={"If-None-Match": etag_1}
    )
    assert res_stale.status_code == 200
    assert res_stale.headers.get("ETag") != etag_1
    assert "New Name" in res_stale.text
    assert "Original Name" not in res_stale.text


def test_master_feed_refreshes_when_newsletter_deleted(
    client: TestClient, db_session: Session
):
    """Deleting a newsletter must drop it from the cached master feed."""
    email_a = f"keep_{uuid.uuid4()}@example.com"
    email_b = f"drop_{uuid.uuid4()}@example.com"
    id_a = client.post(
        "/newsletters", json={"name": "Keep NL", "sender_emails": [email_a]}
    ).json()["id"]
    id_b = client.post(
        "/newsletters", json={"name": "Drop NL", "sender_emails": [email_b]}
    ).json()["id"]

    for nid, subj in ((id_a, "Keep Entry"), (id_b, "Drop Entry")):
        client.post(
            f"/newsletters/{nid}/entries",
            json={
                "subject": subj,
                "body": "<p>Content</p>",
                "message_id": f"<entry_{uuid.uuid4()}@test.com>",
            },
        )

    res_1 = client.get("/feeds/all")
    assert res_1.status_code == 200
    assert "Drop Entry" in res_1.text

    # Delete the second newsletter; its entries should leave the master feed.
    assert client.delete(f"/newsletters/{id_b}").status_code == 200

    res_2 = client.get("/feeds/all")
    assert res_2.status_code == 200
    assert "Keep Entry" in res_2.text
    assert "Drop Entry" not in res_2.text


def test_feed_cache_deleted_on_newsletter_delete(client: TestClient, db_session: Session):
    """Test that deleting a newsletter cleans up its corresponding cache entry."""
    unique_email = f"del_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Delete Test NL", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    entry_data = {
        "subject": "Delete Test Entry",
        "body": "<p>Content</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # Populates cache
    res = client.get(f"/feeds/{newsletter_id}")
    assert res.status_code == 200

    # Cache record exists
    assert db_session.query(FeedCache).filter(FeedCache.feed_id == newsletter_id).count() == 1

    # Delete newsletter
    del_res = client.delete(f"/newsletters/{newsletter_id}")
    assert del_res.status_code == 200

    # Cache record is gone
    assert db_session.query(FeedCache).filter(FeedCache.feed_id == newsletter_id).count() == 0
