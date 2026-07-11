import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.core.database import get_db
from app.core.hashing import get_password_hash
from app.models.settings import Settings as SettingsModel
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@lru_cache(maxsize=1)
def _get_env_password_hash():
    """Get and cache the password hash from environment variables."""
    if env_settings.auth_password:
        return get_password_hash(env_settings.auth_password)
    return None


# In-memory cache of the resolved auth credentials. Auth config changes rarely
# (env is static; DB changes only via settings updates), so caching this removes
# a DB query from every protected route and every feed request. Cleared by
# clear_auth_credentials_cache() on settings writes. Process-local; assumes a
# single worker, like the other in-memory caches.
_auth_credentials_cache: dict[str, dict] = {}


def _get_auth_credentials(db: Session) -> dict:
    """Get auth credentials, prioritizing environment variables. Cached in memory."""
    if "creds" in _auth_credentials_cache:
        return _auth_credentials_cache["creds"]

    # Env vars take precedence
    if env_settings.auth_username and env_settings.auth_password:
        creds = {
            "username": env_settings.auth_username,
            "password_hash": _get_env_password_hash(),
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

    _auth_credentials_cache["creds"] = creds
    return creds


def clear_auth_credentials_cache() -> None:
    """Invalidate the cached auth credentials (call after a settings change)."""
    _auth_credentials_cache.clear()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a new access token."""
    if not env_settings.secret_key:
        raise ValueError("SECRET_KEY is not set, cannot create access tokens.")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, env_settings.secret_key, algorithm=env_settings.algorithm
    )
    return encoded_jwt


def protected_route(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Dependency to protect routes with JWTs."""
    auth_creds = _get_auth_credentials(db)

    # If no auth credentials are set up, access is allowed.
    if not auth_creds.get("username") or not auth_creds.get("password_hash"):
        return

    # Check HttpOnly cookies if Authorization header token is missing
    if token is None:
        token = request.cookies.get("authToken")

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not env_settings.secret_key:
        # This is an internal server error because auth is configured but the key is missing.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY is not configured on the server.",
        )

    try:
        payload = jwt.decode(
            token, env_settings.secret_key, algorithms=[env_settings.algorithm]
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # Check if the username from the token matches the configured username
    correct_username = secrets.compare_digest(
        token_data.username, auth_creds["username"]
    )
    if not correct_username:
        raise credentials_exception

    return token_data.username


def is_auth_enabled(db: Session = Depends(get_db)):
    """Dependency to check if auth is enabled."""
    auth_creds = _get_auth_credentials(db)
    return bool(auth_creds.get("username"))
