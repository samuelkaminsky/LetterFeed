import secrets
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.core.database import get_db
from app.core.hashing import get_password_hash
from app.core.logging import get_logger
from app.models.settings import Settings as SettingsModel
from app.schemas.auth import TokenData

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_WINDOW_SECONDS = 300.0
_LOGIN_TRACKER_MAX_IPS = 1024
_failed_login_lock = threading.Lock()
_failed_login_attempts: OrderedDict[str, list[float]] = OrderedDict()


@lru_cache(maxsize=4)
def _get_env_password_hash(password: str) -> str:
    """Get and cache the password hash from environment variables."""
    return get_password_hash(password)


# In-memory cache of the resolved auth credentials. Auth config changes rarely
# (env is static; DB changes only via settings updates), so caching this removes
# a DB query from every protected route and every feed request. Cleared by
# clear_auth_credentials_cache() on settings writes. Process-local; assumes a
# single worker, like the other in-memory caches.
_auth_credentials_cache: dict[str, dict[str, str]] = {}
_auth_credentials_cache_lock = threading.Lock()


def _get_auth_credentials(db: Session) -> dict[str, str]:
    """Get auth credentials, prioritizing environment variables. Cached in memory."""
    with _auth_credentials_cache_lock:
        if "creds" in _auth_credentials_cache:
            return _auth_credentials_cache["creds"]

    # Env vars take precedence
    if env_settings.auth_username and env_settings.auth_password:
        creds: dict[str, str] = {
            "username": env_settings.auth_username,
            "password_hash": _get_env_password_hash(env_settings.auth_password),
        }
    else:
        # Then check DB
        db_settings = db.query(SettingsModel).first()
        if db_settings and db_settings.auth_username and db_settings.auth_password_hash:
            creds = {
                "username": db_settings.auth_username,
                "password_hash": db_settings.auth_password_hash,
            }
        else:
            creds = {}

    with _auth_credentials_cache_lock:
        _auth_credentials_cache["creds"] = creds
        return creds


def clear_auth_credentials_cache() -> None:
    """Invalidate cached auth credentials and reset failed-login rate-limit state."""
    with _auth_credentials_cache_lock:
        _auth_credentials_cache.clear()
    with _failed_login_lock:
        _failed_login_attempts.clear()


def check_login_rate_limit(client_ip: str) -> None:
    """Raise HTTP 429 if the client IP has exceeded the failed-login window limit."""
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    with _failed_login_lock:
        attempts = _failed_login_attempts.get(client_ip)
        if not attempts:
            return
        recent = [ts for ts in attempts if ts > cutoff]
        if recent:
            _failed_login_attempts[client_ip] = recent
            _failed_login_attempts.move_to_end(client_ip)
        else:
            _failed_login_attempts.pop(client_ip, None)
            return

        if len(recent) >= _LOGIN_MAX_ATTEMPTS:
            retry_after = max(1, int(recent[0] + _LOGIN_WINDOW_SECONDS - now) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


def record_failed_login(client_ip: str) -> None:
    """Record a failed login attempt for the client IP in a bounded LRU map."""
    now = time.monotonic()
    cutoff = now - _LOGIN_WINDOW_SECONDS
    with _failed_login_lock:
        recent = [ts for ts in _failed_login_attempts.get(client_ip, []) if ts > cutoff]
        recent.append(now)
        _failed_login_attempts[client_ip] = recent
        _failed_login_attempts.move_to_end(client_ip)
        while len(_failed_login_attempts) > _LOGIN_TRACKER_MAX_IPS:
            _failed_login_attempts.popitem(last=False)


def clear_failed_logins(client_ip: str) -> None:
    """Clear failed login tracking for a client IP after a successful login."""
    with _failed_login_lock:
        _failed_login_attempts.pop(client_ip, None)


def create_access_token(
    data: dict[str, str], expires_delta: timedelta | None = None
) -> str:
    """Create a new access token."""
    if not env_settings.secret_key:
        raise ValueError("SECRET_KEY is not set, cannot create access tokens.")
    to_encode: dict[str, object] = dict(data)
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, env_settings.secret_key, algorithm=env_settings.algorithm
    )


def _verify_token_for_creds(
    token: str | None, auth_creds: dict[str, str]
) -> str | None:
    """Validate a JWT against configured credentials, returning username or None."""
    if not token or not env_settings.secret_key:
        return None
    try:
        payload = jwt.decode(
            token, env_settings.secret_key, algorithms=[env_settings.algorithm]
        )
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            return None
        token_data = TokenData(username=username)
    except InvalidTokenError:
        return None

    if token_data.username is None or not secrets.compare_digest(
        token_data.username, auth_creds["username"]
    ):
        return None

    return token_data.username


def protected_route(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> str | None:
    """Dependency to protect routes with JWTs."""
    auth_creds = _get_auth_credentials(db)

    # If no auth credentials are set up, access is allowed in dev so first-run
    # setup is frictionless. In production this fails CLOSED instead: an
    # unconfigured instance must not serve protected routes (e.g. /imap/settings,
    # which could otherwise be used to redirect IMAP login and exfiltrate stored
    # credentials). Configure LETTERFEED_AUTH_USERNAME / LETTERFEED_AUTH_PASSWORD
    # (or the settings row) before deploying.
    if not auth_creds.get("username") or not auth_creds.get("password_hash"):
        if env_settings.production:
            logger.error(
                "Blocked a protected request: authentication is not configured while "
                "running in PRODUCTION. Set LETTERFEED_AUTH_USERNAME and "
                "LETTERFEED_AUTH_PASSWORD to enable access."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not configured on the server.",
            )
        return None

    # Check HttpOnly cookies if Authorization header token is missing
    if token is None:
        token = request.cookies.get("authToken")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not env_settings.secret_key:
        # This is an internal server error because auth is configured but the key is missing.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY is not configured on the server.",
        )

    username = _verify_token_for_creds(token, auth_creds)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return username


def get_auth_status(
    request: Request,
    token: str | None,
    db: Session,
) -> dict[str, bool]:
    """Return whether auth is enabled and whether the current request is authenticated."""
    auth_creds = _get_auth_credentials(db)
    auth_enabled = bool(auth_creds.get("username") and auth_creds.get("password_hash"))
    if not auth_enabled:
        return {
            "auth_enabled": False,
            "authenticated": not bool(env_settings.production),
        }

    effective_token = token if token is not None else request.cookies.get("authToken")
    authenticated = _verify_token_for_creds(effective_token, auth_creds) is not None
    return {"auth_enabled": True, "authenticated": authenticated}


def is_auth_enabled(db: Session = Depends(get_db)) -> bool:
    """Dependency to check if auth is enabled."""
    auth_creds = _get_auth_credentials(db)
    return bool(auth_creds.get("username"))
