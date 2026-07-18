from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crud.settings import create_or_update_settings
from app.schemas.settings import SettingsCreate


def test_auth_status_disabled(client: TestClient):
    """Test auth status when auth is disabled."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.json() == {"auth_enabled": False}


def test_auth_status_enabled(client: TestClient, db_session: Session):
    """Test auth status when auth is enabled."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    response = client.get("/auth/status")
    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True}


def test_login_endpoint(client: TestClient, db_session: Session):
    """Test the /auth/login endpoint directly."""
    # Setup auth credentials in the database
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # Test with correct credentials
    login_data = {"username": "admin", "password": "password"}
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200
    json_response = response.json()
    assert "access_token" in json_response
    assert json_response["token_type"] == "bearer"

    # Test with incorrect password
    login_data["password"] = "wrongpassword"
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401

    # Test with incorrect username
    login_data["username"] = "wronguser"
    login_data["password"] = "password"
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 401

    # Test with no credentials
    response = client.post("/auth/login")
    assert response.status_code == 422  # FastAPI validation error for missing form data


def test_protected_route_no_auth(client: TestClient, db_session: Session):
    """Test accessing a protected route without auth enabled."""
    # Health is not protected, newsletters is.
    response = client.get("/newsletters")
    assert response.status_code == 200


def test_protected_route_fails_closed_in_production(
    client: TestClient, db_session: Session
):
    """In production with no auth configured, protected routes fail closed (503)."""
    with patch("app.core.auth.env_settings") as mock_env:
        # No auth configured via env, and no settings row exists in the DB.
        mock_env.auth_username = None
        mock_env.auth_password = None
        mock_env.production = True

        response = client.get("/newsletters")
        assert response.status_code == 503


def test_protected_route_with_auth_fail(client: TestClient, db_session: Session):
    """Test accessing a protected route with auth enabled but wrong credentials."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    response = client.get("/newsletters")
    assert response.status_code == 401

    response = client.get(
        "/newsletters", headers={"Authorization": "Bearer wrongtoken"}
    )
    assert response.status_code == 401


def test_protected_route_with_auth_success(client: TestClient, db_session: Session):
    """Test accessing a protected route with auth enabled and correct credentials."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # First, log in to get a token
    login_data = {"username": "admin", "password": "password"}
    response = client.post("/auth/login", data=login_data)
    token = response.json()["access_token"]

    # Then, use the token to access the protected route
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/newsletters", headers=headers)
    assert response.status_code == 200


def test_unprotected_route_with_auth(client: TestClient, db_session: Session):
    """Test that feed endpoint is not protected."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # Log in to get a token
    login_data = {"username": "admin", "password": "password"}
    login_response = client.post("/auth/login", data=login_data)
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create a newsletter to get a feed from
    newsletter_data = {"name": "Test Newsletter", "sender_emails": ["test@test.com"]}
    create_response = client.post("/newsletters", json=newsletter_data, headers=headers)
    newsletter_id = create_response.json()["id"]

    response = client.get(f"/feeds/{newsletter_id}")
    assert response.status_code == 200


def test_auth_with_env_vars(client: TestClient):
    """Test authentication using environment variables."""
    with patch("app.core.auth.env_settings") as mock_env_settings:
        mock_env_settings.auth_username = "env_admin"
        mock_env_settings.auth_password = "env_password"
        mock_env_settings.secret_key = "test-secret"
        mock_env_settings.algorithm = "HS256"
        mock_env_settings.access_token_expire_minutes = 30

        # Log in to get a token
        login_data = {"username": "env_admin", "password": "env_password"}
        login_response = client.post("/auth/login", data=login_data)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/newsletters", headers=headers)
        assert response.status_code == 200

        response = client.get(
            "/newsletters", headers={"Authorization": "Bearer wrongtoken"}
        )
        assert response.status_code == 401

        response = client.get("/auth/status")
        assert response.status_code == 200
        assert response.json() == {"auth_enabled": True}


def test_login_sets_cookie(client: TestClient, db_session: Session):
    """Test that /auth/login sets the authToken cookie."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    login_data = {"username": "admin", "password": "password"}
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200
    assert "authToken" in response.cookies


def test_protected_route_with_cookie_success(client: TestClient, db_session: Session):
    """Test accessing a protected route using only the authToken cookie."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # First, log in to get a token and set cookie
    login_data = {"username": "admin", "password": "password"}
    response = client.post("/auth/login", data=login_data)
    assert "authToken" in response.cookies

    # Then access the protected route without authorization headers, relying on cookies
    response = client.get("/newsletters")
    assert response.status_code == 200


def test_logout_endpoint(client: TestClient, db_session: Session):
    """Test that /auth/logout deletes the authToken cookie."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # First, log in
    login_data = {"username": "admin", "password": "password"}
    response = client.post("/auth/login", data=login_data)
    assert "authToken" in response.cookies

    # Log out
    response = client.post("/auth/logout")
    assert response.status_code == 200
    # The cookie should either be deleted or set to an empty string with an expired age
    cookie = response.cookies.get("authToken")
    assert cookie is None or cookie == ""


def test_verify_auth_endpoint(client: TestClient, db_session: Session):
    """Test the /auth/verify endpoint behavior."""
    settings_data = SettingsCreate(
        imap_server="test.com",
        imap_username="test",
        imap_password="password",
        auth_username="admin",
        auth_password="password",
    )
    create_or_update_settings(db_session, settings_data)

    # Unauthenticated verify should fail (returns 401)
    response = client.get("/auth/verify")
    assert response.status_code == 401

    # Authenticated verify should succeed
    login_data = {"username": "admin", "password": "password"}
    client.post("/auth/login", data=login_data)
    response = client.get("/auth/verify")
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["username"] == "admin"
