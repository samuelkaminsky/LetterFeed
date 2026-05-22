import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Prefix to distinguish encrypted values from plaintext
ENCRYPTION_PREFIX = "enc_fernet:"


def _get_encryption_key() -> bytes:
    """Derive a 32-byte key for Fernet from the application's SECRET_KEY."""
    secret = settings.secret_key or "default_unsafe_development_key_for_letterfeed"
    # Ensure key is exactly 32-bytes and urlsafe base64 encoded
    hashed = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(hashed)


def encrypt_string(value: str | None) -> str | None:
    """Encrypt a string using Fernet.

    Returns the encrypted string prefixed with ENCRYPTION_PREFIX.
    If input is None or empty, returns the original value.
    """
    if not value:
        return value

    # If it's already encrypted, don't double-encrypt
    if value.startswith(ENCRYPTION_PREFIX):
        return value

    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_bytes = f.encrypt(value.encode())
        return f"{ENCRYPTION_PREFIX}{encrypted_bytes.decode()}"
    except Exception as e:
        logger.error(f"Failed to encrypt string: {e}", exc_info=True)
        # Fallback to returning original value to avoid breaking user flow in worst-case
        return value


def decrypt_string(value: str | None) -> str | None:
    """Decrypt a string if it is encrypted with Fernet.

    If the string does not have the ENCRYPTION_PREFIX, it is returned as-is
    (which handles plaintext/legacy credentials automatically).
    """
    if not value:
        return value

    if not value.startswith(ENCRYPTION_PREFIX):
        # Already plaintext or not encrypted yet
        return value

    try:
        raw_token = value[len(ENCRYPTION_PREFIX) :]
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted_bytes = f.decrypt(raw_token.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt string: {e}", exc_info=True)
        # Fallback to returning original value to maintain usability
        return value
