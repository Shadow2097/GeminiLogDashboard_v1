import sqlite3
import os
from contextlib import contextmanager

# The database file location relative to the project root
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_PATH = os.path.join(DB_DIR, "dashboard.db")

def get_db_path():
    """Returns the absolute path to the database file."""
    return DB_PATH

@contextmanager
def get_connection():
    """Context manager for SQLite connections, ensuring data directory exists and auto-committing/closing."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
