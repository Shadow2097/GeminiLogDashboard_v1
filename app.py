import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import hashlib
from datetime import datetime

from src.database.schema import init_db
from src.database.connection import get_connection
from src.parser.incremental_loader import ingest_logs
from src.metrics.token_counter import count_tokens, get_setting
from src.metrics.heuristics import detect_pleasantries, check_context_debt, run_compression_audit

# Initialize page settings
st.set_page_config(
    page_title="Gemini Log Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom styling for a premium dark interface
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

/* Glassmorphism containers */
div[data-testid="stMetric"] {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 15px 20px;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}

.stTabs [data-baseweb="tab"] {
    font-size: 1.1rem;
    font-weight: 500;
    padding: 10px 20px;
}

.warning-card {
    background-color: #272111;
    border-left: 5px solid #eab308;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 10px 0;
    color: #ffedd5;
    font-weight: 500;
}

.info-card {
    background-color: #0f1c2e;
    border-left: 5px solid #38bdf8;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 10px 0;
    color: #e0f2fe;
    font-weight: 500;
}

.success-card {
    background-color: #0d2216;
    border-left: 5px solid #22c55e;
    padding: 12px 16px;
    border-radius: 6px;
    margin: 10px 0;
    color: #dcfce7;
    font-weight: 500;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
}

.metric-box {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}

.metric-title {
    color: #94a3b8;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}

.metric-val {
    font-size: 2rem;
    font-weight: 700;
    color: #38bdf8;
}

.metric-sub {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# Ensure database is initialized on startup
init_db()

# Auto scan logs on startup
try:
    ingest_logs()
except Exception as e:
    st.sidebar.error(f"Auto-ingest failed: {e}")

# Database helper functions
def save_setting(key, value):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )

# Sidebar Configuration
st.sidebar.title("🛠️ Settings & Controls")

api_key = get_setting("api_key")
new_api_key = st.sidebar.text_input("Gemini API Key", value=api_key, type="password", help="Saved locally to SQLite settings.")
if new_api_key != api_key:
    save_setting("api_key", new_api_key)
    st.sidebar.success("API key updated!")
    st.rerun()

logs_dir = get_setting("logs_directory")
new_logs_dir = st.sidebar.text_input("Logs Directory", value=logs_dir)
if new_logs_dir != logs_dir:
    if os.path.isdir(new_logs_dir):
        save_setting("logs_directory", new_logs_dir)
        st.sidebar.success("Logs directory updated!")
        st.rerun()
    else:
        st.sidebar.error("Invalid folder directory path.")

# Sync logs trigger
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rescan Logs Directory", use_container_width=True):
    with st.spinner("Parsing logs..."):
        updated, turns = ingest_logs()
        st.sidebar.success(f"Scanned! Updated {updated} sessions, loaded {turns} new turns.")
        st.rerun()

# Pricing Config Collapse
with st.sidebar.expander("💰 Customize Pricing rates"):
    f_in = st.number_input("Flash Input Rate ($/1M)", value=float(get_setting("flash_input_rate") or 0.075), format="%.4f")
    f_out = st.number_input("Flash Output Rate ($/1M)", value=float(get_setting("flash_output_rate") or 0.30), format="%.4f")
    p_in = st.number_input("Pro Input Rate ($/1M)", value=float(get_setting("pro_input_rate") or 1.25), format="%.4f")
    p_out = st.number_input("Pro Output Rate ($/1M)", value=float(get_setting("pro_output_rate") or 5.00), format="%.4f")
    
    if st.button("Save Rates", use_container_width=True):
        save_setting("flash_input_rate", str(f_in))
        save_setting("flash_output_rate", str(f_out))
        save_setting("pro_input_rate", str(p_in))
        save_setting("pro_output_rate", str(p_out))
        st.success("Rates saved!")
        st.rerun()

# Main Application Title
st.title("📊 Gemini Log & Token Efficiency Dashboard")
st.markdown("Monitor and optimize your local AntiGravity LLM interactions and token consumption.")

# Tab setup
tab_overview, tab_explorer, tab_advice, tab_playground = st.tabs([
    "📈 Overview Dashboard", 
    "💬 Session Explorer", 
    "💡 Advice",
    "🔍 Prompt Auditor & Playground"
])

# ----------------- TAB 1: OVERVIEW -----------------
with tab_overview:
    # Query high-level aggregates
    with get_connection() as conn:
        totals = conn.execute("""
            SELECT 
                COUNT(*) as session_count,
                SUM(turn_count) as total_turns,
                SUM(total_input_tokens) as total_input,
                SUM(total_output_tokens) as total_output,
                SUM(total_cost) as total_cost
            FROM sessions
        """).fetchone()
        
    if totals and totals["session_count"] > 0:
        total_sessions = totals["session_count"]
        total_turns = totals["total_turns"] or 0
        total_input = totals["total_input"] or 0
        total_output = totals["total_output"] or 0
        total_tokens = total_input + total_output
        total_cost = totals["total_cost"] or 0.0
        
        # Display custom metrics boxes
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-box">
                <div class="metric-title">Total Sessions</div>
                <div class="metric-val">{total_sessions:,}</div>
                <div class="metric-sub">Discovered workspaces</div>
            </div>
            <div class="metric-box">
                <div class="metric-title">Total Cost</div>
                <div class="metric-val">${total_cost:.4f}</div>
                <div class="metric-sub">USD aggregate</div>
            </div>
            <div class="metric-box">
                <div class="metric-title">Total Tokens</div>
                <div class="metric-val">{total_tokens:,}</div>
                <div class="metric-sub">{total_input:,} In / {total_output:,} Out</div>
            </div>
            <div class="metric-box">
                <div class="metric-title">Total Turns</div>
                <div class="metric-val">{total_turns:,}</div>
                <div class="metric-sub">Planner & User Steps</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Plotly cost trends over time
        with get_connection() as conn:
            # Aggregate sessions by date (ignoring HH:MM:SS)
            df_trends = pd.read_sql_query("""
                SELECT 
                    date(created_at) as date,
                    SUM(total_cost) as daily_cost,
                    SUM(total_input_tokens + total_output_tokens) as daily_tokens,
                    COUNT(*) as daily_sessions
                FROM sessions
                WHERE created_at IS NOT NULL AND created_at != ''
                GROUP BY date
                ORDER BY date ASC
            """, conn)
            
        if not df_trends.empty:
            st.subheader("📅 Activity and Cost Trends")
            
            fig = go.Figure()
            # Daily Cost Bar
            fig.add_trace(go.Bar(
                x=df_trends["date"],
                y=df_trends["daily_cost"],
                name="Daily Cost ($)",
                marker_color="#38bdf8",
                yaxis="y"
            ))
            
            # Daily Token Line
            fig.add_trace(go.Scatter(
                x=df_trends["date"],
                y=df_trends["daily_tokens"],
                name="Daily Tokens",
                line=dict(color="#f43f5e", width=3),
                yaxis="y2"
            ))
            
            # Layout configuration for a dual-axis visual style
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="Date"),
                yaxis=dict(title=dict(text="Daily Cost (USD)", font=dict(color="#38bdf8")), tickfont=dict(color="#38bdf8")),
                yaxis2=dict(
                    title=dict(text="Daily Tokens", font=dict(color="#f43f5e")), 
                    tickfont=dict(color="#f43f5e"),
                    overlaying="y", 
                    side="right"
                ),
                legend=dict(x=0.01, y=0.99),
                margin=dict(l=40, r=40, t=20, b=40)
            )
            st.plotly_chart(fig, use_container_width=True)
            
        # Session summary list
        st.subheader("📂 Discovered Conversation Sessions")
        with get_connection() as conn:
            df_sessions = pd.read_sql_query("""
                SELECT 
                    session_id as [Session ID],
                    title as [Title],
                    turn_count as [Turns],
                    total_cost as [Cost ($)],
                    (total_input_tokens + total_output_tokens) as [Total Tokens],
                    efficiency_score as [Efficiency Score (%)]
                FROM sessions
                ORDER BY created_at DESC
            """, conn)
            
        if not df_sessions.empty:
            # Format display
            df_sessions["Cost ($)"] = df_sessions["Cost ($)"].apply(lambda val: f"${val:.4f}")
            df_sessions["Total Tokens"] = df_sessions["Total Tokens"].apply(lambda val: f"{val:,}")
            df_sessions["Efficiency Score (%)"] = df_sessions["Efficiency Score (%)"].apply(lambda val: f"{val:.1f}%")
            
            st.dataframe(df_sessions, use_container_width=True, hide_index=True)
        else:
            st.info("No conversation sessions found. Click 'Rescan Logs Directory' in the sidebar.")
            
    else:
        st.markdown(
            '<div class="info-card">💡 No logs have been parsed yet. Enter your logs path in the sidebar and click <b>Rescan Logs Directory</b>.</div>',
            unsafe_allow_html=True
        )

# ----------------- TAB 2: EXPLORER -----------------
with tab_explorer:
    st.markdown('<div id="session-explorer-top"></div>', unsafe_allow_html=True)
    with get_connection() as conn:
        sessions_dropdown = conn.execute("SELECT session_id, title FROM sessions ORDER BY created_at DESC").fetchall()
        
    if sessions_dropdown:
        options = {f"{s['title']} ({s['session_id'][:8]}...)": s["session_id"] for s in sessions_dropdown}
        selected_option = st.selectbox("Select Conversation Session", options=list(options.keys()))
        selected_session_id = options[selected_option]
        
        # Load stats for selected session
        with get_connection() as conn:
            sess = conn.execute("""
                SELECT turn_count, total_input_tokens, total_output_tokens, total_cost, efficiency_score 
                FROM sessions WHERE session_id = ?
            """, (selected_session_id,)).fetchone()
            
            turns_data = conn.execute("""
                SELECT step_index, source, type, status, created_at, content, model, input_tokens, output_tokens, cost
                FROM turns WHERE session_id = ? ORDER BY step_index ASC
            """, (selected_session_id,)).fetchall()
            
        if sess and turns_data:
            # Styled metrics columns
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Cost", f"${sess['total_cost']:.5f}")
            col2.metric("Total Tokens", f"{sess['total_input_tokens'] + sess['total_output_tokens']:,}", f"{sess['total_input_tokens']:,} In / {sess['total_output_tokens']:,} Out", delta_color="off")
            col3.metric("Turns", f"{sess['turn_count']}")
            
            # Score coloring
            score = sess['efficiency_score']
            if score >= 15.0:
                score_str = f"🟢 {score:.1f}% (High)"
            elif score >= 5.0:
                score_str = f"🟡 {score:.1f}% (Moderate)"
            else:
                score_str = f"🔴 {score:.1f}% (Low - High Context Debt)"
            col4.metric("Efficiency Rating", score_str)
            
            # Cumulative Context Growth Line Chart
            df_sess_turns = pd.DataFrame([dict(t) for t in turns_data])
            df_sess_turns["cumulative_cost"] = df_sess_turns["cost"].cumsum()
            
            # Accumulate input context size step-by-step
            # For displaying context growth, we trace the input tokens of model calls (which represents active history size)
            context_growth = []
            current_context = 0
            for idx, row in df_sess_turns.iterrows():
                # We can trace prompt context size as sum of content tokens so far
                current_context += count_tokens(row["content"])
                context_growth.append(current_context)
            df_sess_turns["active_context_tokens"] = context_growth
            
            st.subheader("📈 Context Accumulation Curve (Context Debt)")
            fig_growth = go.Figure()
            fig_growth.add_trace(go.Scatter(
                x=df_sess_turns["step_index"],
                y=df_sess_turns["active_context_tokens"],
                mode="lines+markers",
                name="Context Size (Tokens)",
                line=dict(color="#38bdf8", width=3),
                marker=dict(size=6)
            ))
            fig_growth.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="Turn / Step Index"),
                yaxis=dict(title="Accumulated Context Tokens"),
                margin=dict(l=40, r=40, t=20, b=40)
            )
            
            selected_data = st.plotly_chart(
                fig_growth, 
                use_container_width=True,
                on_select="rerun",
                selection_mode="points"
            )
            
            if selected_data and "selection" in selected_data:
                points = selected_data["selection"].get("points", [])
                if points:
                    clicked_step_idx = points[0].get("x")
                    if clicked_step_idx is not None:
                        st.components.v1.html(f"""
                        <script>
                            setTimeout(() => {{
                                const element = window.parent.document.getElementById("step-card-{clicked_step_idx}");
                                if (element) {{
                                    element.scrollIntoView({{ behavior: "smooth", block: "center" }});
                                }}
                            }}, 100);
                        </script>
                        """, height=0, width=0)
            
            # Transcript Explorer
            st.subheader("💬 Conversation Transcript & Insights")
            for t in turns_data:
                source = t["source"]
                step_idx = t["step_index"]
                created = t["created_at"]
                content = t["content"] or ""
                model_used = t["model"] or "Gemini"
                in_tok = t["input_tokens"] or 0
                out_tok = t["output_tokens"] or 0
                turn_cost = t["cost"] or 0.0
                
                # Determine display roles
                if source == "MODEL":
                    role = "assistant"
                    label = f"🤖 Model ({model_used})"
                elif source == "SYSTEM":
                    role = "system"
                    label = f"⚙️ System / Tool Output"
                else:
                    role = "user"
                    label = f"👤 User Input"
                    
                with st.chat_message(role):
                    st.markdown(f'<div id="step-card-{step_idx}"></div>', unsafe_allow_html=True)
                    st.markdown(f"**{label}** &nbsp;•&nbsp; *Step {step_idx}* &nbsp;•&nbsp; *{created}*")
                    st.text(content)
                    
                    # Heuristics warnings
                    pleasantries = detect_pleasantries(content)
                    if pleasantries:
                        p_str = ", ".join([f"'{p}'" for p in pleasantries])
                        st.markdown(
                            f'<div class="warning-card">⚠️ <b>Pleasantry Filter Match:</b> Matched low-value phrases: {p_str}. These add to your input context debt on every turn.</div>',
                            unsafe_allow_html=True
                        )
                        
                    if source == "MODEL" and in_tok > 0:
                        debt_info = check_context_debt(in_tok, out_tok)
                        if debt_info["debt_heavy"]:
                            st.markdown(
                                f'<div class="warning-card">💡 <b>Context Debt Warning:</b> {debt_info["message"]}</div>',
                                unsafe_allow_html=True
                            )
                            
                        # Show token breakdown
                        st.markdown(
                            f"<code style='color: #a8a29e; background: #292524; padding: 2px 6px; border-radius: 4px;'>"
                            f"Tokens: {in_tok:,} In / {out_tok:,} Out &nbsp;|&nbsp; Cost: ${turn_cost:.5f}"
                            f"</code>",
                            unsafe_allow_html=True
                        )
                    
                    # Back to Top Link
                    st.markdown(
                        f'<div style="text-align: right; margin-top: 10px;"><a href="#session-explorer-top" target="_self" style="color: #38bdf8; text-decoration: none; font-size: 0.8rem; font-weight: 500;">▲ Back to Top</a></div>',
                        unsafe_allow_html=True
                    )
    else:
        st.info("No conversation sessions loaded. Please configure the logs path and sync.")

# ----------------- TAB 3: ADVICE -----------------
with tab_advice:
    st.subheader("💡 Prompt Optimization & History Advice")
    st.markdown("Review actionable suggestions to optimize your prompt styles and reduce context debt.")
    
    pleasantry_candidates = []
    context_debt_candidates = []
    
    with get_connection() as conn:
        # Query potential pleasantry turns (User turns that are not dismissed)
        user_rows = conn.execute("""
            SELECT t.turn_id, t.session_id, t.step_index, t.content, t.created_at, s.title 
            FROM turns t 
            JOIN sessions s ON t.session_id = s.session_id 
            WHERE (t.source != 'MODEL' AND t.source != 'SYSTEM') AND t.is_dismissed = 0
            ORDER BY t.created_at DESC
        """).fetchall()
        
        # Query potential context debt turns (Model turns that triggered warnings and are not dismissed)
        model_rows = conn.execute("""
            SELECT t.turn_id, t.session_id, t.step_index, t.input_tokens, t.output_tokens, t.cost, t.created_at, s.title 
            FROM turns t 
            JOIN sessions s ON t.session_id = s.session_id 
            WHERE t.source = 'MODEL' AND t.is_dismissed = 0 
              AND (t.input_tokens > 40000 OR (t.input_tokens > 8000 AND t.input_tokens / CAST(MAX(1, t.output_tokens) AS REAL) > 15.0))
            ORDER BY t.created_at DESC
        """).fetchall()
        
        # Process pleasantries
        for row in user_rows:
            pleasantries = detect_pleasantries(row["content"])
            if pleasantries:
                pleasantry_candidates.append({
                    "type": "pleasantry",
                    "turn_id": row["turn_id"],
                    "session_id": row["session_id"],
                    "step_index": row["step_index"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                    "session_title": row["title"],
                    "pleasantries": pleasantries
                })
                
        # Process context debt triggers
        for row in model_rows:
            user_trigger = conn.execute("""
                SELECT turn_id, step_index, content, created_at 
                FROM turns 
                WHERE session_id = ? AND step_index < ? AND (source != 'MODEL' AND source != 'SYSTEM')
                ORDER BY step_index DESC LIMIT 1
            """, (row["session_id"], row["step_index"])).fetchone()
            
            if user_trigger:
                context_debt_candidates.append({
                    "type": "context_debt",
                    "turn_id": row["turn_id"],
                    "user_turn_id": user_trigger["turn_id"],
                    "session_id": row["session_id"],
                    "step_index": user_trigger["step_index"],
                    "model_step_index": row["step_index"],
                    "content": user_trigger["content"],
                    "created_at": user_trigger["created_at"],
                    "session_title": row["title"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cost": row["cost"]
                })
                
    advice_items = pleasantry_candidates + context_debt_candidates
    advice_items.sort(key=lambda x: x["created_at"], reverse=True)
    
    if not advice_items:
        st.markdown(
            '<div class="success-card">✅ <b>Outstanding!</b> No low-value pleasantries or high context debt warnings detected. Your prompting is highly efficient!</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(f"Found **{len(advice_items)}** prompt optimization opportunities. Review them below:")
        
        for item in advice_items:
            card_key = item["turn_id"]
            
            with st.container():
                st.markdown("---")
                col_header, col_actions = st.columns([3, 1])
                
                with col_header:
                    st.markdown(f"**Session:** {item['session_title']} &nbsp;•&nbsp; *Step {item['step_index']}*")
                    if item["type"] == "pleasantry":
                        st.markdown(
                            f'<span style="background-color: #272111; color: #f59e0b; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">⚠️ PLEASANTRY FILTER</span>', 
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**Phrases matched:** {', '.join([f'\"{p}\"' for p in item['pleasantries']])}")
                    else:
                        ratio = item['input_tokens'] / max(1, item['output_tokens'])
                        st.markdown(
                            f'<span style="background-color: #2e100a; color: #f43f5e; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">🚨 HIGH CONTEXT DEBT ({ratio:.1f}x)</span>', 
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"**Spike Details:** Consumed **{item['input_tokens']:,}** input tokens to get **{item['output_tokens']:,}** output tokens. Cost: **${item['cost']:.5f}**."
                        )
                        
                with col_actions:
                    if st.button("Dismiss Advice", key=f"dismiss_{card_key}", use_container_width=True):
                        with get_connection() as conn:
                            conn.execute("UPDATE turns SET is_dismissed = 1 WHERE turn_id = ?", (item["turn_id"],))
                            if item["type"] == "context_debt":
                                conn.execute("UPDATE turns SET is_dismissed = 1 WHERE turn_id = ?", (item["user_turn_id"],))
                        st.success("Dismissed!")
                        st.rerun()
                        
                st.markdown("**Original Prompt:**")
                st.code(item["content"], wrap_lines=True)
                
                with st.expander("🪄 Optimize this prompt"):
                    st.markdown("Click below to let Gemini Flash rewrite this prompt and measure expected token savings.")
                    if st.button("Optimize Prompt", key=f"opt_btn_{card_key}"):
                        with st.spinner("Rewriting..."):
                            audit = run_compression_audit(item["content"])
                            if "error" in audit:
                                st.error(audit["error"])
                            else:
                                st.markdown(f"**Savings:** {audit['savings_ratio'] * 100.0:.1f}% (-{audit['savings_tokens']} tokens)")
                                col_o, col_opt = st.columns(2)
                                with col_o:
                                    st.markdown("Original:")
                                    st.code(item["content"], wrap_lines=True)
                                with col_opt:
                                    st.markdown("Optimized Suggestions:")
                                    st.code(audit["optimized_prompt"], wrap_lines=True)

# ----------------- TAB 4: PLAYGROUND -----------------
with tab_playground:
    st.subheader("🔍 Prompt Auditor")
    st.markdown("Paste your proposed prompt below to measure its length, detect pleasantries, and audit compression savings.")
    
    test_prompt = st.text_area("Proposed Prompt", height=150, placeholder="Type your prompt here...")
    
    if test_prompt:
        # Quick token count
        p_tokens = count_tokens(test_prompt)
        pleasantries_found = detect_pleasantries(test_prompt)
        
        st.markdown("### 📊 Basic Metrics")
        col_tok, col_pls = st.columns(2)
        col_tok.metric("Raw Tokens", f"{p_tokens}")
        
        if pleasantries_found:
            col_pls.error(f"⚠️ {len(pleasantries_found)} pleasantries found")
            st.markdown(f"**Matched pleasantry words:** {', '.join(pleasantries_found)}")
        else:
            col_pls.success("✅ No low-value pleasantries found")
            
        # Compression Audit
        st.markdown("---")
        st.markdown("### 🧠 LLM-in-the-Loop Compression Audit")
        st.markdown("Submit this prompt to Gemini Flash to generate an equivalent, token-optimized version.")
        
        if st.button("Run Compression Audit"):
            with st.spinner("Analyzing prompt with Gemini..."):
                audit_result = run_compression_audit(test_prompt)
                
                if "error" in audit_result:
                    st.error(audit_result["error"])
                else:
                    # Metrics columns
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Original Tokens", f"{audit_result['original_tokens']}")
                    m2.metric("Optimized Tokens", f"{audit_result['optimized_tokens']}")
                    m3.metric("Savings (%)", f"{audit_result['savings_ratio'] * 100.0:.1f}%", f"-{audit_result['savings_tokens']} tokens")
                    
                    # Side-by-side comparison
                    col_orig, col_opt = st.columns(2)
                    with col_orig:
                        st.markdown("**Original Prompt**")
                        st.code(test_prompt, wrap_lines=True)
                    with col_opt:
                        st.markdown("**Optimized Suggestion**")
                        st.code(audit_result["optimized_prompt"], wrap_lines=True)
