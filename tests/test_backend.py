import os
import sys

# Ensure the project root directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database.schema import init_db
from src.database.connection import get_db_path, get_connection
from src.metrics.token_counter import count_tokens, get_heuristic_token_count
from src.parser.incremental_loader import ingest_logs

def run_tests():
    print("--- Starting Backend Validation Tests ---")
    
    # 1. Initialize DB Schema
    print("1. Initializing SQLite Database...")
    init_db()
    
    db_path = get_db_path()
    print(f"   Database successfully created/located at: {db_path}")
    if not os.path.exists(db_path):
        raise AssertionError("Database file was not created!")
        
    # 2. Test Token Counting
    print("2. Testing token counting mechanisms...")
    text = "Hello world! This is a simple validation script testing our token counter heuristics."
    heuristic_cnt = get_heuristic_token_count(text)
    cached_cnt = count_tokens(text)
    print(f"   Heuristic count: {heuristic_cnt} | API/Cached count: {cached_cnt}")
    if cached_cnt <= 0:
        raise AssertionError("Token counting returned invalid result (< 1) for non-empty string.")
        
    # 3. Test Database Connection and settings table values
    print("3. Testing database transactions and settings defaults...")
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'flash_input_rate'").fetchone()
        if not row or float(row["value"]) != 0.075:
            raise AssertionError("Default pricing rates are missing or incorrect in settings.")
        print(f"   Settings checked. Default flash input rate is: ${row['value']}")
        
    # 4. Ingestion test run
    print("4. Executing log parser ingestion dry-run...")
    sessions_updated, turns_added = ingest_logs()
    print(f"   Ingestion completed: {sessions_updated} sessions updated, {turns_added} turns added.")
    
    print("\n[SUCCESS] All Backend Tests Passed Successfully!")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\n[FAIL] Validation Test Failed: {e}", file=sys.stderr)
        sys.exit(1)
