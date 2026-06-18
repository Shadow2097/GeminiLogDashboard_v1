from src.database.connection import get_connection
from src.parser.log_reader import extract_model_change
from src.metrics.token_counter import count_tokens

def get_pricing_rates():
    """Retrieves standard pricing rates from the database settings table."""
    rates = {}
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM settings WHERE key LIKE '%_rate'").fetchall()
            for row in rows:
                rates[row["key"]] = float(row["value"])
    except Exception:
        pass
        
    # Default fallbacks if settings missing or error occurs
    defaults = {
        "flash_input_rate": 0.075,
        "flash_output_rate": 0.30,
        "pro_input_rate": 1.25,
        "pro_output_rate": 5.00
    }
    for k, v in defaults.items():
        if k not in rates:
            rates[k] = v
            
    return rates

def calculate_session_costs(turns_list):
    """
    Computes model, input/output tokens, and cost for each turn in a session.
    Reconstructs the accumulated history of previous turns for input token counts.
    turns_list: list of dicts representing raw parsed turns, sorted by step_index.
    """
    rates = get_pricing_rates()
    active_model = "Gemini 3.5 Flash"
    accumulated_content = []
    updated_turns = []
    
    for turn in turns_list:
        content = turn.get("content", "") or ""
        source = turn.get("source", "")
        
        # Check for model changes in the turn content (typically USER prompts contain setting changes)
        model_change = extract_model_change(content)
        if model_change:
            active_model = model_change
            
        # Determine model tier rates (USD per 1,000,000 tokens)
        is_pro = "pro" in active_model.lower()
        model_key = "pro" if is_pro else "flash"
        
        input_rate = rates.get(f"{model_key}_input_rate", 1.25 if is_pro else 0.075) / 1_000_000
        output_rate = rates.get(f"{model_key}_output_rate", 5.00 if is_pro else 0.30) / 1_000_000
        
        if source == "MODEL":
            # Reconstruct the accumulated context (turns 0 to N-1)
            context_text = "\n".join(accumulated_content)
            input_tokens = count_tokens(context_text)
            output_tokens = count_tokens(content)
            cost = (input_tokens * input_rate) + (output_tokens * output_rate)
        else:
            # Non-model turns are input context only and do not charge output tokens directly
            input_tokens = 0
            output_tokens = 0
            cost = 0.0
            
        # Accumulate content for subsequent steps' context
        accumulated_content.append(content)
        
        updated_turn = dict(turn)
        updated_turn["model"] = active_model
        updated_turn["input_tokens"] = input_tokens
        updated_turn["output_tokens"] = output_tokens
        updated_turn["cost"] = cost
        updated_turns.append(updated_turn)
        
    return updated_turns
