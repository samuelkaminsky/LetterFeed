import imaplib
import re

from app.core.logging import get_logger

"""IMAP utility functions for connecting to mail servers and fetching folders."""

logger = get_logger(__name__)


def _parse_folder_name(folder_str: str) -> str | None:
    """Parse folder name from IMAP list response."""
    match = re.search(r'"([^"]+)"\s*$', folder_str)
    if match:
        return match.group(1)
    else:
        parts = folder_str.split()
        if parts:
            return parts[-1].strip('"')
    return None


def _test_imap_connection(server, username, password):
    """Test the IMAP connection with the given credentials."""
    logger.info(f"Testing IMAP connection to {server} for user {username}")
    try:
        mail = imaplib.IMAP4_SSL(server, timeout=15)
        mail.login(username, password)
        mail.logout()
        logger.info("IMAP connection successful")
        return True, "Connection successful"
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        return False, str(e)


def get_folders(server, username, password):
    """Fetch a list of IMAP folders from the mail server."""
    logger.info(f"Fetching IMAP folders from {server} for user {username}")
    try:
        mail = imaplib.IMAP4_SSL(server, timeout=15)
        mail.login(username, password)
        status, folders = mail.list()
        mail.logout()
        if status == "OK":
            folder_list = []
            for folder in folders:
                try:
                    folder_str = folder.decode("utf-8", "ignore")
                    parsed_name = _parse_folder_name(folder_str)
                    if parsed_name:
                        folder_list.append(parsed_name)
                except Exception as ex:
                    logger.warning(f"Failed to parse folder line {folder}: {ex}")
            logger.info(f"Found {len(folder_list)} folders")
            return folder_list
        logger.warning(f"Failed to list IMAP folders, status: {status}")
        return []
    except Exception as e:
        logger.error(f"Error fetching IMAP folders: {e}")
        return []
