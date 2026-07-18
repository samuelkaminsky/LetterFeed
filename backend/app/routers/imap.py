from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.imap import _test_imap_connection, get_folders
from app.core.logging import get_logger
from app.core.scheduler import reschedule_email_job
from app.crud.settings import create_or_update_settings, get_settings
from app.schemas.settings import Settings, SettingsCreate
from app.services.email_processor import ProcessingInProgressError, process_emails

logger = get_logger(__name__)
router = APIRouter()


@router.get("/imap/settings", response_model=Settings)
def read_settings(db: Session = Depends(get_db)):
    """Retrieve IMAP settings."""
    logger.info("Request to read IMAP settings")
    settings = get_settings(db)
    if not settings:
        logger.warning("IMAP settings not found")
        raise HTTPException(status_code=404, detail="IMAP settings not found")
    return settings


@router.post("/imap/settings", response_model=Settings)
def update_settings(settings: SettingsCreate, db: Session = Depends(get_db)):
    """Update IMAP settings."""
    logger.info("Request to update IMAP settings")
    updated = create_or_update_settings(db=db, settings=settings)
    # Apply the (possibly changed) check interval to the running scheduler so it
    # takes effect without requiring a restart.
    reschedule_email_job(updated.email_check_interval)
    return updated


@router.post("/imap/test")
def test_connection(
    settings_data: SettingsCreate | None = None,
    db: Session = Depends(get_db),
):
    """Test the IMAP connection with current or provided settings."""
    logger.info("Request to test IMAP connection")

    if settings_data:
        # Use provided test settings
        server = settings_data.imap_server
        username = settings_data.imap_username

        # If password is provided, use it. If not, fallback to database password if matching username
        if settings_data.imap_password:
            password = settings_data.imap_password
        else:
            db_settings = get_settings(db, with_password=True)
            if db_settings and db_settings.imap_username == username:
                password = db_settings.imap_password
            else:
                password = ""
    else:
        # Use saved settings
        db_settings = get_settings(db, with_password=True)
        if not db_settings:
            logger.error("IMAP settings not found, cannot test connection")
            raise HTTPException(status_code=404, detail="IMAP settings not found")
        server = db_settings.imap_server
        username = db_settings.imap_username
        password = db_settings.imap_password

    is_successful, message = _test_imap_connection(
        server=server,
        username=username,
        password=password,
    )

    if not is_successful:
        logger.warning(f"IMAP connection test failed: {message}")
        raise HTTPException(status_code=400, detail=message)

    logger.info("IMAP connection test successful")
    return {"message": message}


@router.get("/imap/folders", response_model=List[str])
def read_folders(db: Session = Depends(get_db)):
    """Retrieve a list of IMAP folders from the configured server."""
    logger.info("Request to fetch IMAP folders")
    settings = get_settings(db, with_password=True)
    if not settings:
        logger.error("IMAP settings not found, cannot fetch folders")
        raise HTTPException(status_code=404, detail="IMAP settings not found")

    folders = get_folders(
        server=settings.imap_server,
        username=settings.imap_username,
        password=settings.imap_password,
    )

    logger.info(f"Found {len(folders)} IMAP folders")
    return folders


@router.post("/imap/process")
def trigger_email_processing(db: Session = Depends(get_db)):
    """Trigger the email processing manually."""
    logger.info("Request to manually trigger email processing")
    try:
        process_emails(db)
        return {"message": "Email processing triggered successfully."}
    except ProcessingInProgressError as e:
        logger.warning("Manual email processing triggered but already in progress.")
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error triggering email processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
