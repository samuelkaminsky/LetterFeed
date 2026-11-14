import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import (
    _get_auth_credentials,
    check_login_rate_limit,
    clear_failed_logins,
    create_access_token,
    get_auth_status,
    oauth2_scheme,
    protected_route,
    record_failed_login,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.hashing import verify_password
from app.schemas.auth import Token

router = APIRouter()


@router.get("/auth/status")
def auth_status(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Check if authentication is enabled and whether the request is authenticated."""
    return get_auth_status(request, token, db)


@router.post("/auth/login", response_model=Token)
def login_for_access_token(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Verify username and password and return an access token."""
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    auth_creds = _get_auth_credentials(db)
    if not auth_creds.get("username") or not auth_creds.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured on the server",
        )

    correct_username = secrets.compare_digest(
        form_data.username, auth_creds["username"]
    )
    correct_password = verify_password(form_data.password, auth_creds["password_hash"])

    if not (correct_username and correct_password):
        record_failed_login(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clear_failed_logins(client_ip)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    try:
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Set secure HttpOnly cookie
    max_age_seconds = int(settings.access_token_expire_minutes * 60)
    response.set_cookie(
        key="authToken",
        value=access_token,
        httponly=True,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        samesite="lax",
        secure=settings.production,
        path="/",
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/logout")
def logout(response: Response):
    """Clear the authToken cookie."""
    response.delete_cookie(
        key="authToken",
        path="/",
        httponly=True,
        secure=settings.production,
        samesite="lax",
    )
    return {"message": "Successfully logged out"}


@router.get("/auth/verify")
def verify_auth(username: str | None = Depends(protected_route)):
    """Verify if the user is authenticated."""
    return {"authenticated": True, "username": username}
