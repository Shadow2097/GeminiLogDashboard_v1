# Project Goals & Scope

This document defines the phases and scope for **GeminiLogDashboard (v1)**.

## Phase 1: Local Log Parser (Command Line Utility)
- [ ] Parse `transcript.jsonl` and `transcript_full.jsonl` files from a user-specified AntiGravity log directory.
- [ ] Extract timestamps, message sources (`USER`, `MODEL`, `SYSTEM`), content, and tool executions.
- [ ] Implement local token counting using the Google Generative AI SDK (`google-generativeai` in Python or `@google/generative-ai` in JS).
- [ ] Model context accumulation per session (each step's input includes all previous history).
- [ ] Export parsed data to a standardized JSON or CSV format.

## Phase 2: Analytics & Efficiency Engine
- [ ] Calculate cumulative cost per session based on configurable model rates (e.g., Gemini 1.5 Flash vs. Gemini 1.5 Pro).
- [ ] Build a heuristic analyzer to flag "low-value" token events (pleasantries, repeated text, etc.).
- [ ] Implement the LLM-in-the-loop optimizer prompt template (sending prompts to Flash to measure redundancy).
- [ ] Generate alerts for "Context Debt" (sessions where input tokens drastically outweigh output tokens).

## Phase 3: Dashboard Web UI
- [ ] Build an interactive dashboard interface (e.g., via a Python Streamlit app or a Vite + React web page).
- [ ] Visualize cost and token usage over time (daily/hourly).
- [ ] Display conversation session profiles (session longevity, total cost, efficiency score).
- [ ] Provide a prompt playground/audit screen where users can test prompt rewrites and see token savings.

## Key Target User Value
* **Save Money / Quota**: Prevents users from wasting active context tokens on stale chat history.
* **Refine Prompting Style**: Teaches users how to write concise, instruction-dense prompts.
* **Determine Project Costs**: Gives visibility into which development actions (like deep codebase searches) are token-heavy.
