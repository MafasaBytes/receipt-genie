"""
Migration: Add items_verified column to receipts table.

Run with: python -m migrations.add_items_verified_column
"""
import sqlite3
import os

DB_PATH = os.environ.get("DATABASE_URL", "receipt_scanner.db")
if DB_PATH.startswith("sqlite:///"):
    DB_PATH = DB_PATH.replace("sqlite:///", "")


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(receipts)")
    columns = [row[1] for row in cursor.fetchall()]

    if "items_verified" not in columns:
        cursor.execute("ALTER TABLE receipts ADD COLUMN items_verified INTEGER NULL")
        conn.commit()
        print("Added items_verified column to receipts table.")
    else:
        print("items_verified column already exists.")

    conn.close()


if __name__ == "__main__":
    migrate()
