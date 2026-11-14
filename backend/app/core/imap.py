"""IMAP utility functions for connecting to mail servers and fetching folders."""

import imaplib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version

from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_app_version() -> str:
    """Return the installed backend package version, falling back to 0.4.0."""
    try:
        return version("letterfeed-backend")
    except PackageNotFoundError:
        return "0.4.0"


def parse_folder_name(folder_str: str) -> str | None:
    """Parse folder name from an IMAP LIST response line."""
    match = re.search(r'"([^"]+)"\s*$', folder_str)
    if match:
        return match.group(1)
    parts = folder_str.split()
    if parts:
        return parts[-1].strip('"')
    return None


def quote_mailbox(name: str) -> str:
    """Quote a mailbox name for use in SELECT/COPY.

    imaplib passes mailbox arguments through verbatim, so names containing
    spaces (e.g. "Newsletter Archive") are sent as two atoms and rejected by
    the server. Always quoting is safe under RFC 3501; a name the operator has
    already wrapped in quotes is normalised first so it isn't double-quoted.
    """
    if len(name) >= 2 and name[0] == name[-1] == '"':
        name = name[1:-1]
    name = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{name}"'


def send_client_id(mail: imaplib.IMAP4_SSL) -> None:
    """Send IMAP client identity for providers that require RFC 2971 ID."""
    imaplib.Commands.setdefault("ID", ("AUTH", "SELECTED"))
    app_version = _get_app_version()
    try:
        mail._simple_command(
            "ID",
            f'("name" "LetterFeed" "version" "{app_version}" "vendor" "LetterFeed")',
        )
    except Exception as e:
        logger.warning(f"Failed to send IMAP ID command: {e}")


@contextmanager
def _imap_connection(server: str, timeout: int = 15) -> Iterator[imaplib.IMAP4_SSL]:
    """Open an IMAP4_SSL connection and ensure logout/socket cleanup on exit."""
    mail = imaplib.IMAP4_SSL(server, timeout=timeout)
    try:
        yield mail
    finally:
        try:
            mail.logout()
        except Exception:
            try:
                mail.shutdown()
            except Exception:
                pass


def _test_imap_connection(
    server: str, username: str, password: str | None
) -> tuple[bool, str]:
    """Test the IMAP connection with the given credentials."""
    if not server or not username or not password:
        return False, "IMAP server, username, and password are required."

    logger.info(f"Testing IMAP connection to {server} for user {username}")
    try:
        with _imap_connection(server, timeout=15) as mail:
            mail.login(username, password)
            send_client_id(mail)
        logger.info("IMAP connection successful")
        return True, "Connection successful"
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        return False, str(e)


def get_folders(server: str, username: str, password: str | None) -> list[str]:
    """Fetch a list of IMAP folders from the mail server."""
    if not server or not username or not password:
        logger.debug("IMAP credentials incomplete; skipping folder fetch.")
        return []

    logger.info(f"Fetching IMAP folders from {server} for user {username}")
    try:
        with _imap_connection(server, timeout=15) as mail:
            mail.login(username, password)
            send_client_id(mail)
            status, folders = mail.list()
        if status == "OK" and folders:
            folder_list: list[str] = []
            for folder in folders:
                if not isinstance(folder, bytes):
                    continue
                try:
                    folder_str = folder.decode("utf-8", "ignore")
                    parsed_name = parse_folder_name(folder_str)
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
