"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings
import logging

logger = logging.getLogger(__name__)

# Configure engine based on database type
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        connect_args={"check_same_thread": False}  # Required for SQLite
    )
else:
    # MySQL/PostgreSQL configuration
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    """
    Test database connection.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database connection test failed: {str(e)}")
        return False

