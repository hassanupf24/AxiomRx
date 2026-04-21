import sqlite3
import contextlib
import logging
from typing import Generator

logger = logging.getLogger(__name__)

DB_PATH = "axiom_rx.db"

@contextlib.contextmanager
def get_db_connection(timeout: float = 5.0) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for secure SQLite database connection handling.
    Includes connection timeout to handle locked database states.
    """
    conn = None
    try:
        # timeout parameter allows sqlite to wait for the lock to be released
        conn = sqlite3.connect(DB_PATH, timeout=timeout)
        
        # Enforce foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Enable Write-Ahead Logging (WAL) for better concurrency and fewer database locks
        conn.execute("PRAGMA journal_mode = WAL;") 
        
        # Configure busy timeout explicitly as an additional fallback
        conn.execute(f"PRAGMA busy_timeout = {int(timeout * 1000)};")
        
        # Return rows as dictionary-like objects for easier direct-to-dict coercion
        conn.row_factory = sqlite3.Row
        
        yield conn
        
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower() or "busy" in str(e).lower():
            logger.error("Database is locked. Another process might be writing to it. Please try again.")
        else:
            logger.error(f"Database operational error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def initialize_database():
    """Create normalized tables for the application."""
    queries = [
        """
        CREATE TABLE IF NOT EXISTS Products (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            Barcode TEXT UNIQUE NOT NULL,
            Category TEXT,
            StockQuantity INTEGER DEFAULT 0,
            ReorderLevel INTEGER DEFAULT 0,
            ExpiryDate DATE,
            UnitPrice REAL NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS Sales (
            TransactionID INTEGER PRIMARY KEY AUTOINCREMENT,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            TotalAmount REAL NOT NULL,
            PaymentMethod TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS SalesDetails (
            TransactionID INTEGER NOT NULL,
            ProductID INTEGER NOT NULL,
            Quantity INTEGER NOT NULL,
            Subtotal REAL NOT NULL,
            PRIMARY KEY (TransactionID, ProductID),
            FOREIGN KEY (TransactionID) REFERENCES Sales(TransactionID) ON DELETE CASCADE,
            FOREIGN KEY (ProductID) REFERENCES Products(ID) ON DELETE RESTRICT
        );
        """
    ]
    
    with get_db_connection() as conn:
        try:
            # Context manager on the connection acts as transaction scope
            # It automatically commits on success, and rolls back on exception
            with conn: 
                for query in queries:
                    conn.execute(query)
            logger.info("Database schema initialized successfully.")
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.error("Failed to initialize database schema: Database is locked.")
            raise
