# Gemini Log Dashboard (GeminiLogDashboard_v1)

A local token efficiency and cost-tracking dashboard for AntiGravity activity logs.

## Project Goal
The primary objective of this project is to parse local AntiGravity activity logs and generate actionable metrics, cost tracking, and optimization suggestions for users to maximize the value and efficiency of their allocated LLM tokens.

---

## Technical Foundation

### 1. Source Log Data
AntiGravity activity logs are stored locally as JSON Lines (`.jsonl`) files.
* **Log Location**: `C:\Users\Mike Markiw\.gemini\antigravity\brain\<conversation-id>\.system_generated\logs\`
* **Key Files**: 
  * `transcript.jsonl` (Compact/truncated version)
  * `transcript_full.jsonl` (Complete, detailed version)
* **Log Entry Structure**:
  ```json
  {
    "step_index": 0,
    "source": "USER_EXPLICIT",
    "type": "USER_INPUT",
    "status": "DONE",
    "created_at": "2026-06-18T13:57:49Z",
    "content": "..."
  }
  ```

### 2. Token Estimation & Calculation
To determine token usage, the dashboard will parse the text within log entries and process it using a Gemini-compatible tokenizer:
* **API Integration**: Google's official `google-generativeai` SDK (for Python) or `@google/generative-ai` SDK (for Node.js/Web).
* **Direct Token Counting**: 
  ```python
  import google.generativeai as genai
  genai.configure(api_key="YOUR_API_KEY")
  model = genai.GenerativeModel("gemini-1.5-flash")
  response = model.count_tokens("your prompt content here")
  print(response.total_tokens)
  ```

---

## Key Metrics & Features to Implement

### A. Cost Modeling
Calculate the cost per turn (step) using standard Gemini pricing models:
$$\text{Cost}_N = (\text{Input Tokens}_N \times \text{Input Rate}) + (\text{Output Tokens}_N \times \text{Output Rate})$$
* **Context Accumulation**: The input of each step $N$ contains all previous steps $0$ through $N-1$ plus system prompts and tools. The calculator must reconstruct this accumulated payload to accurately determine input token counts.
* **Model Specific Rates**: Parse user settings changes (e.g., `<USER_SETTINGS_CHANGE>` tags in logs) to apply the correct pricing rates.

### B. Usage Over Time
* Reconstruct and visualize token usage and costs over time (e.g., daily aggregates or 5-hour blocks) using the `created_at` timestamp.
* Map and plot cumulative token growth curve per conversation session.

### C. Prompt Optimization & Efficiency Scoring
Help users refine their prompt styles to minimize wasteful token consumption.
1. **Redundancy Scoring (LLM-in-the-loop)**:
   * Periodically send prompts to a cheap, fast model (like Gemini Flash) to perform "compression audits".
   * Ask the model to rewrite the prompt concisely while retaining 100% intent.
   * Calculate the redundancy score:
     $$\text{Redundancy Score} = 1 - \frac{\text{Optimized Tokens}}{\text{Original Tokens}}$$
2. **Context Growth Warnings**:
   * Flag turns that cause a major spike in context size (e.g., when a user pastes a massive log file or reads a large codebase).
   * Notify the user when starting a new session would be more cost-effective (e.g., when input history size dwarfs output token length).
3. **Filler & Pleasantry Detection**:
   * Run heuristics to flag low-value tokens such as pleasantries ("please," "thank you") or repetitive instructions.

---

## Future Roadmap / Architecture
* **Parser Backend**: Python (using `pandas` and `google-generativeai`) to ingest log files and output formatted usage data.
* **UI Frontend**: A clean, modern local web UI (e.g., using Streamlit, Vite + React, or a lightweight dashboard framework) to display visual graphs, warnings, and history summaries.
