import os
import re
import hashlib
from src.database.connection import get_connection

# Regex to match UUID-like directory names
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

def calculate_file_hash(file_path):
    """Calculates a quick MD5 hash of the first 64KB of a file to check for resets or changes."""
    hasher = hashlib.md5()
    try:
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "rb") as f:
            buf = f.read(65536)
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception:
        return ""

def scan_log_directory(base_dir):
    """
    Scans base_dir for conversation log folders.
    Returns a list of dicts with file path, size, modification time, and session ID.
    """
    log_files = []
    if not base_dir or not os.path.isdir(base_dir):
        return log_files
        
    try:
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            if os.path.isdir(item_path) and UUID_PATTERN.match(item):
                logs_dir = os.path.join(item_path, ".system_generated", "logs")
                if os.path.isdir(logs_dir):
                    # Prefer transcript_full.jsonl as it is not truncated, fallback to transcript.jsonl
                    full_path = os.path.join(logs_dir, "transcript_full.jsonl")
                    compact_path = os.path.join(logs_dir, "transcript.jsonl")
                    
                    target_path = None
                    if os.path.isfile(full_path):
                        target_path = full_path
                    elif os.path.isfile(compact_path):
                        target_path = compact_path
                        
                    if target_path:
                        stat = os.stat(target_path)
                        log_files.append({
                            "session_id": item,
                            "file_path": os.path.abspath(target_path),
                            "file_size": stat.st_size,
                            "last_modified": stat.st_mtime
                        })
    except Exception as e:
        print(f"Error scanning log directory {base_dir}: {e}")
        
    return log_files

def get_file_parse_state(file_path):
    """Retrieves the last saved state of a file from the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT file_size, file_hash, last_read_line FROM processed_files WHERE file_path = ?",
            (file_path,)
        ).fetchone()
        if row:
            return dict(row)
        return None

def update_file_parse_state(file_path, size, file_hash, last_line, last_modified):
    """Updates the database with the current parsing progress for a file."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO processed_files (file_path, file_size, file_hash, last_read_line, last_modified)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size = excluded.file_size,
                file_hash = excluded.file_hash,
                last_read_line = excluded.last_read_line,
                last_modified = excluded.last_modified
            """,
            (file_path, size, file_hash, last_line, last_modified)
        )
