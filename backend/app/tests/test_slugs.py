import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.slug import sanitize_slug


@pytest.mark.parametrize(
    "input_slug, expected_slug",
    [
        ("Hello World", "hello-world"),
        ("  leading and trailing spaces  ", "leading-and-trailing-spaces"),
        ("!@#$%^&*()", None),
        ("a-b_c d", "a-b-c-d"),
        ("SLUG IN CAPS", "slug-in-caps"),
        (None, None),
        ("", None),
    ],
)
def test_sanitize_slug(input_slug, expected_slug):
    """Test the slug sanitization function with various inputs."""
    assert sanitize_slug(input_slug) == expected_slug


def test_create_newsletter_with_slug(client: TestClient, db_session: Session):
    """Test creating a newsletter with a custom slug."""
    newsletter_data = {
        "name": "My Test Newsletter",
        "slug": "my-custom-slug",
        "sender_emails": ["test@example.com"],
    }
    response = client.post("/newsletters", json=newsletter_data)
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "my-custom-slug"

    # Verify the feed URL uses the slug
    feed_response = client.get(f"/feeds/{data['slug']}")
    assert feed_response.status_code == 200


def test_create_newsletter_with_sanitization(client: TestClient, db_session: Session):
    """Test creating a newsletter with a slug that needs sanitization."""
    newsletter_data = {
        "name": "Another Test",
        "slug": "  Another Slug With Spaces!  ",
        "sender_emails": ["test2@example.com"],
    }
    response = client.post("/newsletters", json=newsletter_data)
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "another-slug-with-spaces"


def test_create_newsletter_without_slug(client: TestClient, db_session: Session):
    """Test creating a newsletter without a slug, expecting it to be None."""
    newsletter_data = {
        "name": "No Slug Newsletter",
        "sender_emails": ["no-slug@example.com"],
    }
    response = client.post("/newsletters", json=newsletter_data)
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] is None

    # Verify the feed URL uses the ID
    feed_response = client.get(f"/feeds/{data['id']}")
    assert feed_response.status_code == 200


def test_create_newsletter_with_conflicting_slug(
    client: TestClient, db_session: Session
):
    """Test creating a newsletter with a slug that already exists."""
    # Create the first newsletter
    client.post(
        "/newsletters",
        json={
            "name": "First",
            "slug": "conflict-slug",
            "sender_emails": ["first@example.com"],
        },
    )

    # Attempt to create a second one with the same slug
    response = client.post(
        "/newsletters",
        json={
            "name": "Second",
            "slug": "conflict-slug",
            "sender_emails": ["second@example.com"],
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Slug already in use"


def test_update_newsletter_with_conflicting_slug(
    client: TestClient, db_session: Session
):
    """Test updating a newsletter to a slug that is already in use by another newsletter."""
    # Create two newsletters
    response1 = client.post(
        "/newsletters",
        json={"name": "First", "slug": "first-slug", "sender_emails": ["1@test.com"]},
    )
    newsletter1_id = response1.json()["id"]

    client.post(
        "/newsletters",
        json={"name": "Second", "slug": "second-slug", "sender_emails": ["2@test.com"]},
    )

    # Try to update the first newsletter to use the second's slug
    update_data = {
        "name": "First Updated",
        "slug": "second-slug",
        "sender_emails": ["1@test.com"],
    }
    response = client.put(f"/newsletters/{newsletter1_id}", json=update_data)
    assert response.status_code == 409
    assert response.json()["detail"] == "Slug already in use"


@pytest.mark.parametrize("bad_slug", ["all", "  ALL  ", "_all_"])
def test_reject_reserved_slug_all(client: TestClient, bad_slug: str):
    """Creating or updating a newsletter with reserved slug 'all' returns 422."""
    create_res = client.post(
        "/newsletters",
        json={
            "name": "Reserved Slug NL",
            "slug": bad_slug,
            "sender_emails": ["reserved@test.com"],
        },
    )
    assert create_res.status_code == 422

    ok_res = client.post(
        "/newsletters",
        json={
            "name": "Valid NL",
            "slug": "valid-slug",
            "sender_emails": ["valid@test.com"],
        },
    )
    assert ok_res.status_code == 200
    nl_id = ok_res.json()["id"]

    update_res = client.put(
        f"/newsletters/{nl_id}",
        json={
            "name": "Valid NL",
            "slug": bad_slug,
            "sender_emails": ["valid@test.com"],
        },
    )
    assert update_res.status_code == 422


def test_slug_based_entry_create_and_delete_clears_cache(client: TestClient):
    """Creating an entry and deleting a newsletter by slug invalidates the ID-keyed feed cache."""
    create_res = client.post(
        "/newsletters",
        json={
            "name": "Slug Cache NL",
            "slug": "my-feed",
            "sender_emails": ["slugcache@test.com"],
        },
    )
    assert create_res.status_code == 200

    # Warm the feed cache before adding an entry
    feed_before = client.get("/feeds/my-feed")
    assert feed_before.status_code == 200
    assert feed_before.text.count("<entry>") == 0

    entry_res = client.post(
        "/newsletters/my-feed/entries",
        json={
            "subject": "Slug Entry",
            "body": "<p>Hello via slug</p>",
            "message_id": "<slug-entry-1@test.com>",
        },
    )
    assert entry_res.status_code == 200

    feed_after_entry = client.get("/feeds/my-feed")
    assert feed_after_entry.status_code == 200
    assert feed_after_entry.text.count("<entry>") == 1

    delete_res = client.delete("/newsletters/my-feed")
    assert delete_res.status_code == 200

    feed_after_delete = client.get("/feeds/my-feed")
    assert feed_after_delete.status_code == 404
