import sqlite3
import logging
from typing import List, Optional, Dict, Any
from database import get_db_connection

logger = logging.getLogger(__name__)

def add_product(name: str, barcode: str, category: str, stock_quantity: int, reorder_level: int, expiry_date: str, unit_price: float) -> Optional[int]:
    """Adds a new product to the database."""
    query = """
        INSERT INTO Products (Name, Barcode, Category, StockQuantity, ReorderLevel, ExpiryDate, UnitPrice)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    with get_db_connection() as conn:
        try:
            with conn: # Commit if successful, rollback if error
                cursor = conn.execute(query, (name, barcode, category, stock_quantity, reorder_level, expiry_date, unit_price))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.error(f"Integrity Error (e.g., duplicate barcode): {e}")
            raise
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.error("Database locked during add_product.")
            raise

def get_product_by_barcode(barcode: str) -> Optional[Dict[str, Any]]:
    """Fetches a product using its barcode."""
    query = "SELECT * FROM Products WHERE Barcode = ?"
    with get_db_connection() as conn:
        cursor = conn.execute(query, (barcode,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_products() -> List[Dict[str, Any]]:
    """Retrieves all products."""
    query = "SELECT * FROM Products"
    with get_db_connection() as conn:
        cursor = conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]

def record_sale(total_amount: float, payment_method: str, items: List[Dict[str, Any]]) -> Optional[int]:
    """
    Records a sale and its details in a single atomic transaction.
    Also deducts stock quantity for each sold product.
    
    `items` format: [{'product_id': int, 'quantity': int, 'subtotal': float}]
    """
    with get_db_connection() as conn:
        try:
            with conn: # Atomic transaction context manager
                # 1. Insert into Sales
                cursor = conn.execute(
                    "INSERT INTO Sales (TotalAmount, PaymentMethod) VALUES (?, ?)",
                    (total_amount, payment_method)
                )
                transaction_id = cursor.lastrowid
                
                # 2. Insert into SalesDetails and update Stock Quantity
                for item in items:
                    conn.execute(
                        """
                        INSERT INTO SalesDetails (TransactionID, ProductID, Quantity, Subtotal)
                        VALUES (?, ?, ?, ?)
                        """,
                        (transaction_id, item['product_id'], item['quantity'], item['subtotal'])
                    )
                    
                    # Deduct from stock
                    conn.execute(
                        "UPDATE Products SET StockQuantity = StockQuantity - ? WHERE ID = ?",
                        (item['quantity'], item['product_id'])
                    )
                return transaction_id
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.error("Database locked during the record_sale transaction.")
            raise
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            raise
