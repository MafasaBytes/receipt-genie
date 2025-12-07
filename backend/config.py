"""
Configuration settings for the Receipt Scanner backend.
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_TITLE: str = "Receipt Scanner API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database Settings
    # Use SQLite for development (no setup required) or MySQL for production
    # SQLite: "sqlite:///./receipt_scanner.db"
    # MySQL: "mysql+pymysql://root:password@localhost:3306/receipt_scanner"
    DATABASE_URL: str = "sqlite:///./receipt_scanner.db"
    DATABASE_ECHO: bool = False
    DATABASE_REQUIRED: bool = False  # If False, app will start even if DB connection fails
    
    # File Storage
    BASE_DIR: Path = Path(__file__).parent
    TEMP_DIR: Path = BASE_DIR / "temp"
    EXPORTS_DIR: Path = BASE_DIR / "exports"
    
    # Ollama LLM Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:latest"  # Default model, will auto-fallback to first available if not found
    OLLAMA_TIMEOUT: int = 480  # 8 minutes per receipt (increased for international receipts with complex VAT calculations)
    
    # Processing Settings
    MAX_FILE_SIZE_MB: int = 50
    SUPPORTED_IMAGE_FORMATS: list = [".png", ".jpg", ".jpeg"]
    
    # YOLO Settings (placeholder)
    YOLO_MODEL_PATH: Optional[str] = None
    YOLO_CONFIDENCE_THRESHOLD: float = 0.5
    
    # OCR Settings
    OCR_LANG: str = "en"  # For PaddleOCR: "en", "ch", "fr", "german", "korean", "japan", etc.
    # For Dutch receipts, you can use: OCR_LANG="en" or install language packs
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Initialize settings
settings = Settings()

# Ensure directories exist
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

