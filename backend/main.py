"""
FastAPI main application.
"""
import sys
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add backend directory to Python path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from database import engine, Base, test_connection
from routers import upload, process, export

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the application."""
    # Startup: Create database tables (only if connection is available)
    try:
        if test_connection():
            Base.metadata.create_all(bind=engine)
            logger.info("[OK] Database tables created successfully")
        else:
            if settings.DATABASE_REQUIRED:
                raise Exception("Database connection required but failed")
            else:
                logger.warning("[WARNING] Database connection failed, but continuing without database")
    except Exception as e:
        if settings.DATABASE_REQUIRED:
            logger.error(f"[FAILED] Database initialization failed: {str(e)}")
            raise
        else:
            logger.warning(f"[WARNING] Database initialization failed, but continuing: {str(e)}")
    
    # Check Ollama connection
    from services.llm_extractor import check_ollama_connection
    if check_ollama_connection():
        logger.info("[OK] Ollama is running and accessible")
    else:
        logger.warning("[WARNING] Ollama is not available. LLM extraction will fail.")
        logger.warning("  Start Ollama with: ollama serve")
        logger.warning("  Pull a model with: ollama pull llama3.2")
    
    # Check OCR availability
    from services.ocr_engine import is_ocr_available
    if is_ocr_available():
        logger.info("[OK] OCR is available (PaddleOCR or pytesseract)")
    else:
        logger.warning("[WARNING] OCR not available. Using placeholder text.")
        logger.warning("  Install PaddleOCR: pip install paddlepaddle paddleocr")
        logger.warning("  Or pytesseract: pip install pytesseract")
    
    logger.info("[OK] Receipt Scanner API is ready!")
    
    yield
    # Shutdown: Cleanup if needed
    pass


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload.router, prefix=settings.API_PREFIX)
app.include_router(process.router, prefix=settings.API_PREFIX)
app.include_router(export.router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Receipt Scanner API",
        "version": settings.API_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

