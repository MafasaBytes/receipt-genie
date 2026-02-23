"""
Migration script to add vat_breakdown and vat_percentage_effective columns to receipts table.

Run this script once to update your existing database schema:
    python -m migrations.add_vat_columns
"""
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from database import engine, test_connection
from config import settings
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Add new VAT columns to receipts table if they don't exist."""
    if not test_connection():
        logger.error("Database connection failed. Cannot run migration.")
        return False
    
    try:
        with engine.connect() as conn:
            # Check if columns already exist
            vat_breakdown_exists = column_exists(conn, 'receipts', 'vat_breakdown')
            vat_percentage_effective_exists = column_exists(conn, 'receipts', 'vat_percentage_effective')
            
            if vat_breakdown_exists and vat_percentage_effective_exists:
                logger.info("✓ Columns 'vat_breakdown' and 'vat_percentage_effective' already exist. Migration not needed.")
                return True
            
            # Determine database type
            is_sqlite = settings.DATABASE_URL.startswith("sqlite")
            
            # Add vat_breakdown column
            if not vat_breakdown_exists:
                if is_sqlite:
                    # SQLite doesn't support JSON type directly, use TEXT
                    logger.info("Adding 'vat_breakdown' column (TEXT for SQLite)...")
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN vat_breakdown TEXT"))
                else:
                    # MySQL/PostgreSQL support JSON
                    logger.info("Adding 'vat_breakdown' column (JSON)...")
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN vat_breakdown JSON"))
                conn.commit()
                logger.info("✓ Added 'vat_breakdown' column")
            else:
                logger.info("✓ Column 'vat_breakdown' already exists")
            
            # Add vat_percentage_effective column
            if not vat_percentage_effective_exists:
                logger.info("Adding 'vat_percentage_effective' column...")
                conn.execute(text("ALTER TABLE receipts ADD COLUMN vat_percentage_effective FLOAT"))
                conn.commit()
                logger.info("✓ Added 'vat_percentage_effective' column")
            else:
                logger.info("✓ Column 'vat_percentage_effective' already exists")
            
            logger.info("✓ Migration completed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"✗ Migration failed: {str(e)}")
        logger.exception("Full error traceback:")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Database Migration: Add VAT Columns")
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

