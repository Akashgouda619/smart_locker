import sqlite3
import os
from config import Config

def get_db_connection():
    """Establishes a connection to the SQLite database with dictionary-like row factory."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys constraint for this connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the database using the schema.sql file."""
    # Ensure database folder exists
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "migrations",
        "schema.sql"
    )
    
    conn = get_db_connection()
    try:
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise e
    finally:
        conn.close()
