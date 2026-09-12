import bcrypt

# bcrypt only looks at the first 72 bytes of the input; bcrypt>=5 raises on
# longer passwords instead of silently truncating (which passlib used to do).
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed one."""
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("ascii"))
    except ValueError:
        # Malformed / non-bcrypt hash stored in the DB
        return False
