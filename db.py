"""
db.py
Single shared MongoDB connection for the whole project.
Every other module imports get_db() / get_fs() from here instead of
creating its own MongoClient. This mirrors the "one shared db.py"
rule from the project brief and keeps the whole app pointed at the
same database no matter which screen is running.
"""

from pymongo import MongoClient
from pymongo.server_api import ServerApi
import gridfs
import sys

# ---------------------------------------------------------------------------
# CONNECTION SETTINGS
# ---------------------------------------------------------------------------
# Local MongoDB Community Server default connection string.
# If you later switch to MongoDB Atlas, just replace this string with the
# connection string Atlas gives you (Connect -> Drivers -> Python) and
# nothing else in the project needs to change.
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "real_estate_db"

_client = None
_db = None
_fs = None


def get_client():
    """Return a singleton MongoClient, creating it on first use."""
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Force a round trip so connection problems surface immediately
            # (at import time) instead of silently, deep inside a CRUD call.
            _client.admin.command("ping")
        except Exception as exc:
            print("=" * 70)
            print("Could not connect to MongoDB.")
            print(f"Tried: {MONGO_URI}")
            print("Make sure MongoDB Community Server is installed and running")
            print("(check the 'MongoDB' service in Windows Services, or run")
            print("'mongod' / 'net start MongoDB' from a terminal).")
            print(f"Original error: {exc}")
            print("=" * 70)
            sys.exit(1)
    return _client


def get_db():
    """Return the shared database handle (real_estate_db)."""
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db


def get_fs():
    """Return a GridFS handle, used to store/retrieve property images."""
    global _fs
    if _fs is None:
        _fs = gridfs.GridFS(get_db())
    return _fs


def ensure_indexes():
    """
    Create a couple of sane indexes on first run. Safe to call every time
    the app starts - create_index() is a no-op if the index already exists.
    """
    db = get_db()
    db.users.create_index("username", unique=True)
    db.properties.create_index([("title", 1)])
    db.properties.create_index([("status", 1)])
    db.clients.create_index([("name", 1)])
    db.agents.create_index([("name", 1)])
    db.inquiries.create_index([("status", 1)])
    db.inquiries.create_index([("client_id", 1)])
    db.inquiries.create_index([("property_id", 1)])
