from .connection import get_connection

def init_db():
    """Initializes the database schema if tables do not exist."""
    with get_connection() as conn:
        # Create processed_files table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_files (
            file_path TEXT PRIMARY KEY,
            file_size INTEGER NOT NULL,
            file_hash TEXT NOT NULL,
            last_read_line INTEGER NOT NULL,
            last_modified REAL NOT NULL
        );
        """)
        
        # Create sessions table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0.0,
            turn_count INTEGER DEFAULT 0,
            efficiency_score REAL DEFAULT 100.0
        );
        """)
        
        # Create turns table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            turn_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            source TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            content TEXT,
            content_hash TEXT NOT NULL,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        );
        """)
        
        # Create token_cache table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS token_cache (
            text_hash TEXT PRIMARY KEY,
            token_count INTEGER NOT NULL
        );
        """)
        
        # Create settings table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        
        # Insert default settings if not exists
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('api_key', '');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('flash_input_rate', '0.075');") # USD per 1M tokens
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('flash_output_rate', '0.30');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pro_input_rate', '1.25');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('pro_output_rate', '5.00');")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('logs_directory', 'C:\\Users\\Mike Markiw\\.gemini\\antigravity\\brain');")
