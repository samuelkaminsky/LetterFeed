import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import is_auth_enabled
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.crud.entries import get_latest_entry_timestamp_cached
from app.crud.feed_cache import (
    compute_feed_etag,
    get_cached_feed,
    get_gzipped_feed,
    set_cached_feed,
)
from app.crud.newsletters import get_newsletter_identity
from app.crud.settings import get_master_feed_token
from app.services.feed_generator import generate_feed, generate_master_feed

logger = get_logger(__name__)
router = APIRouter()


def _to_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime, assuming naive values are UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _etag_matches(if_none_match: str, etag: str) -> bool:
    """Weak If-None-Match comparison (RFC 9110 13.1.2).

    Proxies such as Cloudflare rewrite our strong ETag to W/"..." when they
    re-compress the body, so readers echo the weak form back. An exact string
    compare would miss it and resend the full feed on every refresh.
    """
    if if_none_match.strip() == "*":
        return True
    opaque = etag.removeprefix("W/")
    return any(
        candidate.strip().removeprefix("W/") == opaque
        for candidate in if_none_match.split(",")
    )


def _accepts_gzip(accept_encoding: str | None) -> bool:
    """Return True if the Accept-Encoding header allows gzip."""
    if not accept_encoding:
        return False
    for part in accept_encoding.split(","):
        coding, _, params = part.strip().partition(";")
        if coding.strip().lower() in ("gzip", "*"):
            q = params.strip().lower().replace(" ", "")
            return q not in ("q=0", "q=0.0", "q=0.00", "q=0.000")
    return False


def _not_modified(
    latest_timestamp: datetime | None,
    etag: str,
    if_none_match: str | None,
    if_modified_since: str | None,
) -> bool:
    """Return True if the client's cached copy is still current (send 304)."""
    if if_none_match and _etag_matches(if_none_match, etag):
        logger.debug("Feed unmodified (ETag match), returning 304")
        return True

    if if_modified_since and latest_timestamp:
        try:
            ims_datetime = parsedate_to_datetime(if_modified_since)
            latest_utc = _to_utc(latest_timestamp)
            if latest_utc.replace(microsecond=0) <= ims_datetime.replace(microsecond=0):
                logger.debug("Feed unmodified since If-Modified-Since, returning 304")
                return True
        except Exception as e:
            logger.warning(f"Error parsing If-Modified-Since header: {e}")

    return False


def _feed_headers(etag: str, latest_timestamp: datetime | None) -> dict[str, str]:
    """Build the response headers common to every feed response."""
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
        "Vary": "Accept-Encoding",
    }
    if latest_timestamp:
        headers["Last-Modified"] = format_datetime(
            _to_utc(latest_timestamp), usegmt=True
        )
    return headers


def _conditional_feed_response(
    db: Session,
    cache_key: str,
    latest_timestamp: datetime | None,
    if_none_match: str | None,
    if_modified_since: str | None,
    generate_fn: Callable[[], str | bytes | None],
    is_head: bool = False,
    accept_encoding: str | None = None,
) -> Response:
    """Serve a feed with ETag/If-Modified-Since handling and DB/memory caching."""
    etag = compute_feed_etag(cache_key, latest_timestamp)
    headers = _feed_headers(etag, latest_timestamp)

    if _not_modified(latest_timestamp, etag, if_none_match, if_modified_since):
        return Response(status_code=304, headers=headers)

    cached_feed = get_cached_feed(db, cache_key, etag)
    if cached_feed is None:
        feed = generate_fn()
        if not feed:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        set_cached_feed(db, cache_key, etag, feed)
        cached_feed = feed

    if is_head:
        content_bytes = (
            cached_feed.encode("utf-8") if isinstance(cached_feed, str) else cached_feed
        )
        headers["Content-Length"] = str(len(content_bytes))
        return Response(content=b"", media_type="application/atom+xml", headers=headers)

    if _accepts_gzip(accept_encoding):
        # Serve the pre-compressed body; GZipMiddleware skips responses that
        # already carry a Content-Encoding.
        headers["Content-Encoding"] = "gzip"
        return Response(
            content=get_gzipped_feed(cache_key, etag, cached_feed),
            media_type="application/atom+xml",
            headers=headers,
        )

    return Response(
        content=cached_feed, media_type="application/atom+xml", headers=headers
    )


@router.api_route("/feeds/all", methods=["GET", "HEAD"])
def get_master_feed(
    request: Request,
    token: str | None = None,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
):
    """Generate a master Atom feed for all newsletters."""
    # Authenticate the master feed if auth is enabled. Both is_auth_enabled and
    # the master token are served from in-memory caches, so a warm secured 304
    # still issues zero DB queries.
    if is_auth_enabled(db):
        master_token = get_master_feed_token(db)
        if (
            not token
            or not master_token
            or not secrets.compare_digest(token, master_token)
        ):
            logger.warning(
                "Unauthorized attempt to access master feed (invalid or missing token)"
            )
            raise HTTPException(
                status_code=401, detail="Unauthorized: Invalid or missing token"
            )

    logger.info("Generating master feed for all newsletters")
    latest_timestamp = get_latest_entry_timestamp_cached(db)

    return _conditional_feed_response(
        db,
        "master",
        latest_timestamp,
        if_none_match,
        if_modified_since,
        lambda: generate_master_feed(db, request=request),
        is_head=(request.method == "HEAD"),
        accept_encoding=request.headers.get("accept-encoding"),
    )


@router.api_route("/feeds/{feed_identifier}", methods=["GET", "HEAD"])
def get_newsletter_feed(
    feed_identifier: str,
    request: Request,
    db: Session = Depends(get_db),
    if_none_match: str | None = Header(default=None),
    if_modified_since: str | None = Header(default=None),
):
    """Generate an Atom feed for a specific newsletter."""
    logger.info(f"Generating feed for newsletter with identifier={feed_identifier}")

    # Lightweight identity resolve (cached) — the conditional/304 hot path never
    # needs the entry count or senders that get_newsletter_by_identifier loads.
    identity = get_newsletter_identity(db, feed_identifier)
    if not identity:
        logger.warning(
            f"Newsletter with identifier={feed_identifier} not found, cannot generate feed."
        )
        raise HTTPException(status_code=404, detail="Newsletter not found")

    newsletter_id, newsletter_slug = identity

    # Secure feeds: restrict access to the cryptographically secure ID (NanoID)
    # to prevent slug guessing when authentication is enabled.
    if newsletter_slug == feed_identifier and is_auth_enabled(db):
        logger.warning(
            f"Blocked guessable slug-based feed access for slug '{feed_identifier}'."
        )
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Guessable slug-based feed access is disabled for security. Please use the secure feed ID.",
        )

    latest_timestamp = get_latest_entry_timestamp_cached(
        db, newsletter_id=newsletter_id
    )

    # Always pass the secure newsletter ID to prevent any internal slug mapping issues.
    return _conditional_feed_response(
        db,
        newsletter_id,
        latest_timestamp,
        if_none_match,
        if_modified_since,
        lambda: generate_feed(
            db,
            newsletter_id,
            request=request,
            limit=settings.newsletter_feed_limit,
        ),
        is_head=(request.method == "HEAD"),
        accept_encoding=request.headers.get("accept-encoding"),
    )
