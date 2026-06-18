# Architecture and Directory Structure

This document outlines the tech stack, components, and directory structure selected for the **Gemini Log Dashboard (v1)**.

---

## Tech Stack Overview

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Language** | **Python 3.x** | Used for both backend processing and frontend interface. |
| **Front-End Dashboard** | **Streamlit** | A web-based UI framework for Python to quickly build data apps. |
| **Data Visualization** | **Plotly / Altair** | Render interactive charts for cost/token usage over time directly within Streamlit. |
| **Datastore** | **SQLite** | A lightweight, file-based relational database to cache token estimates and track ingestion state. |
| **Token Estimator** | **Google Generative AI SDK** | The official `google-generativeai` package to accurately estimate input and output tokens. |

---

## Directory Structure

To keep the project modular and clean, we will organize the files as follows:

```text
GeminiLogDashboard_v1/
│
├── README.md                  # Project overview and specifications
├── project_goals.md           # Phase scope checklist
├── architecture.md            # This architecture document
├── requirements.txt           # Python library dependencies
│
├── app.py                     # Streamlit Main Dashboard Application
│
├── src/                       # Source code directory
│   ├── __init__.py
│   │
│   ├── database/              # SQLite Database Handler
│   │   ├── __init__.py
│   │   ├── connection.py      # SQLite connection manager
│   │   └── schema.py          # Table schemas for state and metrics
│   │
│   ├── parser/                # Log Parser & Incremental Loader
│   │   ├── __init__.py
│   │   ├── log_reader.py      # Reads JSONL transcripts
│   │   └── state_tracker.py   # Computes file hashes/stamps to skip duplicates
│   │
│   └── metrics/               # Costs, Tokens, and Optimizations
│       ├── __init__.py
│       ├── token_counter.py   # Counts tokens via official SDK
│       ├── cost_calculator.py # Simulates context accumulation and costs
│       └── heuristics.py      # Flags filler words and high context debt
│
└── data/                      # Local data cache
    └── dashboard.db           # SQLite database file (git-ignored)
```

---

## Key Flow & Component Interaction

1. **Ingestion & State Tracking**:
   * The dashboard/CLI starts and scans the log directory.
   * `state_tracker.py` checks the SQLite database table `processed_logs` for file paths, sizes, and hashes.
   * If a log file is new or modified (size increased), only the new lines are read.

2. **Parsing & Token Cache**:
   * `log_reader.py` parses the new JSONL lines.
   * Before calling the API, `token_counter.py` checks a local cache table in SQLite (`token_cache`) using the hash of the text.
   * If the text isn't cached, it calls the Gemini API's `count_tokens` endpoint, returns the count, and stores it in the cache to prevent redundant API calls and save quota.

3. **Metrics Calculation**:
   * `cost_calculator.py` tracks model changes (via `<USER_SETTINGS_CHANGE>` parsed entries) and applies the cumulative cost formulas.
   * The calculated results are stored in SQLite (`sessions` and `turns` tables).

4. **Visualization**:
   * `app.py` queries the SQLite database directly and renders tables, charts, and recommendations in the browser window via Streamlit.
