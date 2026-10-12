"""users table."""

from ..db import execute, query_one


def find_by_id(user_id):
    return query_one("SELECT id, email, display_name FROM users WHERE id = %s", (user_id,))


def find_by_email(email):
    """Public fields only (no password hash)."""
    return query_one("SELECT id, email, display_name FROM users WHERE email = %s", (email,))


def find_credentials(email):
    """Including password_hash, for logging in."""
    return query_one("SELECT * FROM users WHERE email = %s", (email,))


def create(email, password_hash, display_name):
    """Raises pymysql IntegrityError if the email is taken."""
    return execute(
        "INSERT INTO users (email, password_hash, display_name) VALUES (%s, %s, %s)",
        (email, password_hash, display_name),
    )
