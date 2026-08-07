"""
auth.py
Login / registration logic. Passwords are never stored in plain text -
only a bcrypt hash is written to MongoDB.
"""

import bcrypt
from db import get_db

VALID_ROLES = ("admin", "agent")


def register_user(username: str, password: str, role: str = "agent"):
    """
    Create a new user document. Returns (success: bool, message: str).
    """
    username = username.strip()
    if not username or not password:
        return False, "Username and password are required."
    if role not in VALID_ROLES:
        return False, f"Role must be one of {VALID_ROLES}."

    db = get_db()
    if db.users.find_one({"username": username}):
        return False, "That username is already taken."

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    db.users.insert_one(
        {
            "username": username,
            "password_hash": password_hash,
            "role": role,
        }
    )
    return True, "Account created. You can now log in."


def login_user(username: str, password: str):
    """
    Verify credentials. Returns the role string ('admin'/'agent') on
    success, or None on failure.
    """
    db = get_db()
    user = db.users.find_one({"username": username.strip()})
    if not user:
        return None
    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        return user["role"]
    return None


def user_count():
    return get_db().users.count_documents({})


def ensure_default_admin():
    """
    Convenience for first run: if no admin exists yet, create one so the
    app isn't a chicken-and-egg problem (can't log in because there's no
    user, can't register the first user's role as admin from the GUI).
    Default login: admin / admin123 - change the password after first login
    by registering a new admin and deleting this one, or extend the GUI
    with a 'change password' screen as a stretch goal.
    """
    db = get_db()
    if not db.users.find_one({"role": "admin"}):
        register_user("admin", "admin123", "admin")
