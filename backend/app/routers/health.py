from fastapi import APIRouter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
def health_check():
    """Perform a health check of the API.

    Includes the deployed git SHA (or "unknown" for local/dev builds) so a
    deploy can be verified with a single request to /health.
    """
    logger.info("Health check endpoint called")
    return {"status": "ok", "version": settings.git_sha}
