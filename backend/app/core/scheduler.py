from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.crud.settings import get_settings
from app.services.email_processor import process_emails

"""Scheduler for background tasks like email processing."""

logger = get_logger(__name__)


def job():
    """Process emails as a scheduled job."""
    logger.info("Scheduler job starting: process_emails")
    db = SessionLocal()
    try:
        process_emails(db)
        logger.info("Scheduler job finished: process_emails")
    except Exception as e:
        logger.error(f"Error in scheduled job process_emails: {e}", exc_info=True)
    finally:
        db.close()


scheduler = BackgroundScheduler()


def start_scheduler_with_interval():
    """Start the scheduler with an interval based on application settings."""
    logger.info("Attempting to start scheduler...")
    db = SessionLocal()
    try:
        settings = get_settings(db)
        interval = settings.email_check_interval if settings else 15
        # Guard against a bad persisted value: minutes<=0 makes APScheduler raise
        # and would leave the job (and email processing) unscheduled.
        interval = max(1, interval)
        logger.info(f"Setting scheduler interval to {interval} minutes")
        scheduler.add_job(
            job,
            "interval",
            minutes=interval,
            id="email_check_job",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.add_job(
                job,
                "date",
                run_date=datetime.now(),
                id="initial_email_check",
                replace_existing=True,
            )
            scheduler.start()
            logger.info("Scheduler started.")
        else:
            logger.info("Scheduler is already running.")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
    finally:
        db.close()


def reschedule_email_job(interval_minutes: int) -> None:
    """Update the running email-check job's interval after a settings change."""
    if not scheduler.running:
        logger.info(
            "Scheduler not running; new interval will apply on next startup."
        )
        return
    interval_minutes = max(1, interval_minutes)
    try:
        scheduler.reschedule_job(
            "email_check_job", trigger="interval", minutes=interval_minutes
        )
        logger.info(f"Rescheduled email check job to every {interval_minutes} minutes.")
    except Exception as e:
        logger.error(f"Failed to reschedule email check job: {e}", exc_info=True)
