from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.auth import protected_route
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.logging import get_logger, setup_logging
from app.core.scheduler import scheduler, start_scheduler_with_interval
from app.crud.settings import create_initial_settings
from app.routers import auth, feeds, health, imap, newsletters


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    setup_logging()
    logger = get_logger(__name__)

    logger.info(f"DATABASE_URL used: {settings.database_url}")
    logger.info("Starting up Letterfeed backend...")
    logger.warning(
        "Letterfeed uses process-local memory caches for performance. Running multiple uvicorn "
        "worker processes is not supported and will result in stale/inconsistent cache state."
    )

    if settings.production and not settings.secret_key:
        logger.warning(
            "SECRET_KEY is not set in production! Login tokens cannot be issued and "
            "stored credentials fall back to an insecure default encryption key. "
            "Set LETTERFEED_SECRET_KEY (e.g. `openssl rand -hex 32`)."
        )

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        create_initial_settings(db)

    start_scheduler_with_interval()
    yield
    if scheduler.running:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
    logger.info("...Letterfeed backend shut down.")


# Disable docs in production
fastapi_kwargs = {}
if settings.production:
    fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

app = FastAPI(lifespan=lifespan, **fastapi_kwargs)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip Compression Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(imap.router, dependencies=[Depends(protected_route)])
app.include_router(newsletters.router, dependencies=[Depends(protected_route)])
app.include_router(feeds.router)
