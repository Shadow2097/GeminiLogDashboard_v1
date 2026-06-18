# Implementation Plan: Gemini Log Dashboard Setup & Core Engine

We will initialize the Python environment, set up the project folder structure, establish the SQLite datastore, write the parser and cache modules, and construct the basic Streamlit frontend.

---

## Proposed Changes

### Environment & Dependencies

#### [NEW] [requirements.txt](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/requirements.txt)
*Already created, containing `streamlit`, `google-generativeai`, `pandas`, and `plotly`.*

---

### 1. Database Layer (`src/database/`)

#### [NEW] [connection.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/database/connection.py)
* Manages the SQLite database connection.
* Auto-creates the data directory (`data/`) if it doesn't exist.

#### [NEW] [schema.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/database/schema.py)
* Sets up tables:
  * `processed_files`: Stores file hashes, sizes, and last read line counts to support incremental parsing.
  * `turns`: Stores parsed conversation turns, prompt contents (hashes to keep DB small or snippets), timestamp, source, token counts, and cost details.
  * `sessions`: Aggregated statistics per conversation ID.
  * `token_cache`: Simple mapping of `text_hash -> token_count` to save API key quota.
  * `settings`: Stores global dashboard settings (like user's API Key and standard rates).

---

### 2. Log Parser Layer (`src/parser/`)

#### [NEW] [state_tracker.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/parser/state_tracker.py)
* Scans the base directory `C:/Users/Mike Markiw/.gemini/antigravity/brain` for log directories.
* Checks file modification times and sizes against `processed_files`.

#### [NEW] [log_reader.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/parser/log_reader.py)
* Parses new JSONL lines from `transcript.jsonl` / `transcript_full.jsonl` files.
* Extracts core metrics: step index, source, type, status, content, and system prompt contexts.

---

### 3. Metrics & Estimations Layer (`src/metrics/`)

#### [NEW] [token_counter.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/metrics/token_counter.py)
* Integrates with `google-generativeai` SDK to fetch exact token counts.
* Implements a local offline fallback (approximate tokenizer based on character/word heuristic) if no API key is set.
* Reads from and writes to the `token_cache` table to optimize execution.

#### [NEW] [cost_calculator.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/src/metrics/cost_calculator.py)
* Models context accumulation (e.g. cumulative input size per turn).
* Maps current costs based on model type (e.g., Gemini 3.5 Flash vs. Pro).

---

### 4. Dashboard Web App

#### [NEW] [app.py](file:///f:/AntiGravityWorkspace/AntiGravityLogDashboard/GeminiLogDashboard_v1/app.py)
* Main entry point for the Streamlit dashboard.
* Integrates a sidebar configuration menu where users can:
  * Manually input/save their Gemini API key to SQLite settings (saved securely locally).
  * Configure custom pricing models (input and output token rates).
  * Select a conversation session from a dropdown menu of auto-discovered sessions.
* Displays charts and summaries using `plotly` and `pandas`.

---

## Verification Plan

### Manual Verification
1. Run terminal setup script to create `.venv` and install `requirements.txt`.
2. Launch the Streamlit application using `streamlit run app.py`.
3. Verify the browser page opens correctly and shows:
   * The sidebar settings menu with API key text input.
   * Auto-discovered conversation sessions (like this current one).
   * A default warning to add an API key (or fall back to the heuristic counter).
