import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.entries import _latest_timestamp_cache
from app.crud.feed_cache import _feed_memory_cache


def test_gzip_compression(client: TestClient, db_session: Session):
    """Test that feeds support Gzip compression when requested."""
    # 1. Create newsletter
    unique_email = f"gzip_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Gzip Test NL", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    # 2. Add an entry with a large body to exceed the 1000-byte Gzip threshold
    entry_data = {
        "subject": "Gzip Entry",
        "body": "<p>" + "A" * 1500 + "</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # Request master feed with Accept-Encoding: gzip
    headers = {"Accept-Encoding": "gzip"}
    response = client.get("/feeds/all", headers=headers)
    
    # It should succeed and indicate gzip encoding
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_last_modified_and_if_modified_since(client: TestClient, db_session: Session):
    """Test that Last-Modified and If-Modified-Since headers work correctly."""
    # 1. Create newsletter
    unique_email = f"perf_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Perf Test NL", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    # 2. Add an entry
    entry_data = {
        "subject": "Perf Entry",
        "body": "<p>Content</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # 3. Request the feed to get headers
    response = client.get(f"/feeds/{newsletter_id}")
    assert response.status_code == 200
    
    last_modified = response.headers.get("Last-Modified")
    etag = response.headers.get("ETag")
    
    assert last_modified is not None
    assert etag is not None

    # 4. Request with If-Modified-Since matching the Last-Modified header
    headers = {"If-Modified-Since": last_modified}
    response_ims = client.get(f"/feeds/{newsletter_id}", headers=headers)
    assert response_ims.status_code == 304

    # 5. Request with If-None-Match matching ETag
    headers_etag = {"If-None-Match": etag}
    response_etag = client.get(f"/feeds/{newsletter_id}", headers=headers_etag)
    assert response_etag.status_code == 304


def test_in_memory_cache_layer(client: TestClient, db_session: Session):
    """Test that the in-memory cache layer gets populated on a feed request."""
    # 1. Create newsletter
    unique_email = f"mem_test_{uuid.uuid4()}@example.com"
    newsletter_data = {"name": "Mem Test NL", "sender_emails": [unique_email]}
    create_response = client.post("/newsletters", json=newsletter_data)
    newsletter_id = create_response.json()["id"]

    entry_data = {
        "subject": "Mem Entry",
        "body": "<p>Content</p>",
        "message_id": f"<entry_{uuid.uuid4()}@test.com>",
    }
    client.post(f"/newsletters/{newsletter_id}/entries", json=entry_data)

    # Clean caches to start fresh
    _feed_memory_cache.clear()
    _latest_timestamp_cache.clear()

    assert newsletter_id not in _feed_memory_cache
    assert newsletter_id not in _latest_timestamp_cache

    # 2. First fetch: populates both caches
    response_1 = client.get(f"/feeds/{newsletter_id}")
    assert response_1.status_code == 200

    assert newsletter_id in _feed_memory_cache
    assert newsletter_id in _latest_timestamp_cache

    # Verify the cached content matches the response
    cached_etag, cached_content = _feed_memory_cache[newsletter_id]
    assert response_1.headers.get("ETag") == cached_etag
    assert response_1.text == cached_content
