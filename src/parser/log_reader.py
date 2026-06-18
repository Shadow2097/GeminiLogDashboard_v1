import json
import os
import re

SETTINGS_CHANGE_PATTERN = re.compile(
    r"changed setting `?Model Selection`? from (?:.*?) to `?([^`\.\n]+)",
    re.IGNORECASE
)

def extract_model_change(content):
    """Parses model selection setting changes from prompt content."""
    if not content:
        return None
    match = SETTINGS_CHANGE_PATTERN.search(content)
    if match:
        # Strip trailing dot, quotes, spaces, and clean up the model name
        val = match.group(1).strip().strip("'\"`().")
        # Remove any extra text like "No need to comment..."
        val = val.split(".")[0].split(" (")[0] # e.g. "Gemini 3.5 Flash"
        return val.strip()
    return None

def read_new_lines(file_path, start_line=0):
    """
    Reads lines from a JSONL log file starting from start_line (0-indexed).
    Returns a list of parsed JSON dicts and the final line count reached.
    """
    parsed_lines = []
    current_line = 0
    if not os.path.exists(file_path):
        return parsed_lines, 0
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if current_line >= start_line:
                    line_str = line.strip()
                    if line_str:
                        try:
                            data = json.loads(line_str)
                            parsed_lines.append(data)
                        except json.JSONDecodeError as je:
                            print(f"Skipping malformed JSON line {current_line} in {file_path}: {je}")
                current_line += 1
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        
    return parsed_lines, current_line
