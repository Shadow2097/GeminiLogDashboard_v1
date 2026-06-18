import re
import google.generativeai as genai
from src.metrics.token_counter import count_tokens, get_setting

# Regex patterns for matching common conversational pleasantries and filler phrases
PLEASANTRIES = [
    r"\bhello\b",
    r"\bhi\b",
    r"\bhey\b",
    r"\bplease\b",
    r"\bthank\s+you\b",
    r"\bthanks\b",
    r"\bhope\s+you\s+are\s+doing\s+well\b",
    r"\bhope\s+this\s+finds\s+you\s+well\b",
    r"\bgood\s+morning\b",
    r"\bgood\s+afternoon\b",
    r"\bgood\s+evening\b",
    r"\bwould\s+you\s+mind\b",
    r"\bcould\s+you\s+please\b",
    r"\bif\s+you\s+don't\s+mind\b"
]

def detect_pleasantries(text):
    """
    Scans text for conversational pleasantries.
    Returns a list of matches.
    """
    if not text:
        return []
    matches = []
    text_lower = text.lower()
    for pattern in PLEASANTRIES:
        if re.search(pattern, text_lower):
            # Clean up boundary markers for display
            clean_match = pattern.replace(r"\b", "").replace(r"\s+", " ")
            matches.append(clean_match)
    return matches

def check_context_debt(input_tokens, output_tokens):
    """
    Analyzes input and output tokens to flag Context Debt spikes.
    Returns a dict with warning details.
    """
    if input_tokens == 0:
        return {"debt_heavy": False, "ratio": 0.0, "message": ""}
        
    ratio = input_tokens / max(1, output_tokens)
    
    # Debt spikes:
    # 1. Total context is massive (> 40k tokens)
    # 2. Ratio of input tokens to output tokens is extremely lopsided (> 15x) for non-trivial requests
    if input_tokens > 40000:
        return {
            "debt_heavy": True,
            "ratio": ratio,
            "message": f"Critical Context Size: The session context has reached {input_tokens:,} tokens. Starting a new chat is highly recommended to clear this context debt."
        }
    elif input_tokens > 8000 and ratio > 15.0:
        return {
            "debt_heavy": True,
            "ratio": ratio,
            "message": f"High Context Debt ({ratio:.1f}x Ratio): You sent {input_tokens:,} input tokens to receive only {output_tokens} output tokens. Resetting context would save quota."
        }
        
    return {"debt_heavy": False, "ratio": ratio, "message": ""}

def run_compression_audit(prompt_text):
    """
    Runs an LLM-in-the-loop compression audit using Gemini 1.5 Flash.
    Returns a comparison of original vs optimized text, token count difference, and savings ratio.
    """
    api_key = get_setting("api_key")
    if not api_key:
        return {"error": "API Key is required to run the LLM-in-the-loop compression audit. Please configure it in Settings."}
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        system_instruction = (
            "You are a prompt optimizer. Rewrite the following user prompt to be as concise, direct, "
            "and instruction-dense as possible, while retaining 100% of the original instructions, "
            "intent, code blocks, parameters, and details. Remove all conversational pleasantries, "
            "preambles, and filler language. Return ONLY the optimized prompt text with no explanation, "
            "introductory phrases, or markdown styling outside the prompt itself."
        )
        
        response = model.generate_content(
            contents=[
                {"role": "user", "parts": [f"{system_instruction}\n\nORIGINAL PROMPT:\n{prompt_text}"]}
            ]
        )
        
        optimized_text = response.text.strip()
        
        # Calculate tokens
        orig_tokens = count_tokens(prompt_text)
        opt_tokens = count_tokens(optimized_text)
        
        savings_tokens = max(0, orig_tokens - opt_tokens)
        savings_ratio = savings_tokens / max(1, orig_tokens)
        
        return {
            "original_prompt": prompt_text,
            "optimized_prompt": optimized_text,
            "original_tokens": orig_tokens,
            "optimized_tokens": opt_tokens,
            "savings_tokens": savings_tokens,
            "savings_ratio": savings_ratio
        }
    except Exception as e:
        return {"error": f"LLM Compression Audit failed: {str(e)}"}
