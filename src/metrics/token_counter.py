import hashlib
import google.generativeai as genai
from src.database.connection import get_connection

_genai_model = None
_active_api_key = None

def get_setting(key):
    """Retrieves a config value from the settings table."""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else ""
    except Exception:
        return ""

def _get_model():
    """Initializes and returns the GenerativeModel instance using the API Key from settings."""
    global _genai_model, _active_api_key
    api_key = get_setting("api_key")
    if not api_key:
        _genai_model = None
        _active_api_key = None
        return None
        
    # Re-initialize if the key has changed
    if _genai_model is None or _active_api_key != api_key:
        try:
            genai.configure(api_key=api_key)
            _genai_model = genai.GenerativeModel("gemini-3.5-flash")
            _active_api_key = api_key
        except Exception as e:
            print(f"Error configuring Google Generative AI SDK: {e}")
            _genai_model = None
            _active_api_key = None
            
    return _genai_model

def get_heuristic_token_count(text):
    """Fallback tokenizer: approximates token count based on typical character-to-token ratio (1 token ~ 4 chars)."""
    if not text:
        return 0
    return max(1, len(text) // 4)

def count_tokens(text):
    """
    Counts the tokens of a text string.
    Checks the local SQLite cache first. If missing, calls Gemini API or falls back to heuristic.
    """
    if not text:
        return 0
        
    text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
    
    # Check cache
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT token_count FROM token_cache WHERE text_hash = ?", (text_hash,)).fetchone()
            if row:
                return row["token_count"]
    except Exception as e:
        print(f"Database error reading token_cache: {e}")
        
    # Calculate
    token_count = None
    model = _get_model()
    if model:
        try:
            response = model.count_tokens(text)
            token_count = response.total_tokens
        except Exception as e:
            # Safe fallback if API call fails (e.g. quota, bad key, network issue)
            print(f"API token counting failed, falling back to heuristic: {e}")
            
    if token_count is None:
        token_count = get_heuristic_token_count(text)
        
    # Save to cache
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO token_cache (text_hash, token_count) VALUES (?, ?)",
                (text_hash, token_count)
            )
    except Exception as e:
        print(f"Database error writing token_cache: {e}")
        
    return token_count
