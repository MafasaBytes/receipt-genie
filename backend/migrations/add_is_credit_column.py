"""
Migration script to add is_credit column to receipts table.

Run this script once to update your existing database schema:
    python -m migrations.add_is_credit_column
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from database import engine, test_connection
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Add is_credit column to receipts table if it doesn't exist."""
    if not test_connection():
        logger.error("Database connection failed. Cannot run migration.")
        return False

    try:
        with engine.connect() as conn:
            if column_exists(conn, 'receipts', 'is_credit'):
                logger.info("✓ Column 'is_credit' already exists. Migration not needed.")
                return True

            logger.info("Adding 'is_credit' column...")
            conn.execute(text("ALTER TABLE receipts ADD COLUMN is_credit INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
            logger.info("✓ Added 'is_credit' column")

            logger.info("✓ Migration completed successfully!")
            return True

    except Exception as e:
        logger.error(f"✗ Migration failed: {str(e)}")
        logger.exception("Full error traceback:")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Database Migration: Add is_credit Column")
    logger.info("=" * 60)

    success = migrate()

    if success:
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error("=" * 60)
        sys.exit(1)
