import os
import hashlib
import re
from src.database.connection import get_connection
from src.parser.state_tracker import (
    scan_log_directory, get_file_parse_state, update_file_parse_state, calculate_file_hash
)
from src.parser.log_reader import read_new_lines
from src.metrics.cost_calculator import calculate_session_costs

def extract_session_title(turns):
    """Generates a human-friendly title based on the first user query in a session."""
    for turn in turns:
        if turn.get("source") == "USER_EXPLICIT" or turn.get("type") == "USER_INPUT":
            content = turn.get("content", "")
            
            # Extract content from USER_REQUEST tags if present
            match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL | re.IGNORECASE)
            if match:
                clean_content = match.group(1).strip()
            else:
                clean_content = re.sub(r"<[^>]+>", "", content).strip()
            
            first_line = clean_content.split("\n")[0].strip()
            if len(first_line) > 55:
                return first_line[:55] + "..."
            return first_line if first_line else "Untitled Session"
    return "Untitled Session"

def ingest_logs():
    """
    Scans the configured log directory, loads new entries,
    calculates token metrics/costs, and saves to database.
    """
    logs_dir = ""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'logs_directory'").fetchone()
            if row:
                logs_dir = row["value"]
    except Exception as e:
        print(f"Error reading logs_directory setting: {e}")
        return 0, 0
        
    if not logs_dir or not os.path.isdir(logs_dir):
        print(f"Invalid logs directory: {logs_dir}")
        return 0, 0
        
    log_files = scan_log_directory(logs_dir)
    sessions_updated = 0
    turns_added = 0
    
    for log_file in log_files:
        file_path = log_file["file_path"]
        session_id = log_file["session_id"]
        file_size = log_file["file_size"]
        last_modified = log_file["last_modified"]
        
        state = get_file_parse_state(file_path)
        current_hash = calculate_file_hash(file_path)
        
        start_line = 0
        if state:
            # Check if file has been reset/shrunk or hash has changed
            if current_hash == state["file_hash"] and file_size >= state["file_size"]:
                start_line = state["last_read_line"]
                
        new_lines, total_lines = read_new_lines(file_path, start_line)
        
        if not new_lines and start_line == total_lines:
            # File is unchanged
            continue
            
        sessions_updated += 1
        turns_added += len(new_lines)
        
        # Retrieve existing database turns for context accumulation reconstruction
        existing_turns = []
        if start_line > 0:
            try:
                with get_connection() as conn:
                    rows = conn.execute(
                        """
                        SELECT step_index, source, type, status, created_at, content, model, input_tokens, output_tokens, cost
                        FROM turns WHERE session_id = ? ORDER BY step_index ASC
                        """,
                        (session_id,)
                    ).fetchall()
                    existing_turns = [dict(row) for row in rows]
            except Exception as e:
                print(f"Error loading existing turns for session {session_id}: {e}")
                
        # Format the new lines
        new_turns = []
        for line_data in new_lines:
            content = line_data.get("content", "") or ""
            new_turns.append({
                "session_id": session_id,
                "step_index": line_data.get("step_index", 0),
                "source": line_data.get("source", ""),
                "type": line_data.get("type", ""),
                "status": line_data.get("status", ""),
                "created_at": line_data.get("created_at", ""),
                "content": content,
                "content_hash": hashlib.md5(content.encode("utf-8")).hexdigest()
            })
            
        # Combine all turns to calculate context accumulation correctly
        all_turns = existing_turns + new_turns
        all_turns.sort(key=lambda x: x["step_index"])
        
        processed_all_turns = calculate_session_costs(all_turns)
        
        # Save session record header
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, processed_all_turns[0]["created_at"] if processed_all_turns else "", "")
                )
        except Exception as e:
            print(f"Error inserting session header: {e}")
            
        # Upsert only the newly parsed turns
        new_processed_turns = processed_all_turns[start_line:]
        try:
            with get_connection() as conn:
                for turn in new_processed_turns:
                    turn_id = f"{session_id}_{turn['step_index']}"
                    conn.execute(
                        """
                        INSERT INTO turns (
                            turn_id, session_id, step_index, source, type, status, created_at, content, content_hash, model, input_tokens, output_tokens, cost
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(turn_id) DO UPDATE SET
                            session_id = excluded.session_id,
                            step_index = excluded.step_index,
                            source = excluded.source,
                            type = excluded.type,
                            status = excluded.status,
                            created_at = excluded.created_at,
                            content = excluded.content,
                            content_hash = excluded.content_hash,
                            model = excluded.model,
                            input_tokens = excluded.input_tokens,
                            output_tokens = excluded.output_tokens,
                            cost = excluded.cost
                        """,
                        (
                            turn_id, session_id, turn["step_index"], turn["source"], turn["type"], turn["status"],
                            turn["created_at"], turn["content"], turn["content_hash"], turn["model"],
                            turn["input_tokens"], turn["output_tokens"], turn["cost"]
                        )
                    )
        except Exception as e:
            print(f"Error saving parsed turns: {e}")
            
        # Re-aggregate total session values
        if processed_all_turns:
            created_at = processed_all_turns[0]["created_at"]
            updated_at = processed_all_turns[-1]["created_at"]
            turn_count = len(processed_all_turns)
            total_input = sum(t.get("input_tokens", 0) or 0 for t in processed_all_turns)
            total_output = sum(t.get("output_tokens", 0) or 0 for t in processed_all_turns)
            total_cost = sum(t.get("cost", 0.0) or 0.0 for t in processed_all_turns)
            title = extract_session_title(processed_all_turns)
            
            # Efficiency score: output / input ratio as a percentage
            efficiency_score = (total_output / max(1, total_input)) * 100.0
            
            try:
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE sessions SET
                            created_at = ?,
                            updated_at = ?,
                            turn_count = ?,
                            total_input_tokens = ?,
                            total_output_tokens = ?,
                            total_cost = ?,
                            efficiency_score = ?,
                            title = ?
                        WHERE session_id = ?
                        """,
                        (created_at, updated_at, turn_count, total_input, total_output, total_cost, efficiency_score, title, session_id)
                    )
            except Exception as e:
                print(f"Error updating session aggregates: {e}")
                
        # Record processing progress
        try:
            update_file_parse_state(file_path, file_size, current_hash, total_lines, last_modified)
        except Exception as e:
            print(f"Error updating file parse state: {e}")
            
    return sessions_updated, turns_added
