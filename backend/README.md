# Receipt Scanner Backend

A FastAPI-based backend system for processing PDFs containing multiple receipts, extracting structured data using OCR and LLM, and exporting results.

## Architecture

```
PDF → Images → YOLO Receipt Detection → OCR → LLM Extract → MySQL → CSV/Excel
```

## Tech Stack

- **FastAPI** - Modern Python web framework
- **SQLAlchemy + MySQL** - Database ORM and storage
- **pypdfium2** - PDF to image conversion
- **PaddleOCR** (placeholder) - Text extraction
- **YOLO** (placeholder) - Receipt detection
- **Ollama** - Local LLM for field extraction
- **Pandas + openpyxl** - CSV/Excel export

## Setup

### 1. Prerequisites

- Python 3.10+
- MySQL server
- Ollama installed and running (for LLM extraction)

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Database Setup

Create a MySQL database:

```sql
CREATE DATABASE receipt_scanner;
```

Update `DATABASE_URL` in `.env` or `config.py`:

```
DATABASE_URL=mysql+pymysql://username:password@localhost:3306/receipt_scanner
```

### 4. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings.

### 5. Run the Server

```bash
# Development mode with auto-reload
python main.py

# Or using uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## API Endpoints

### Upload

- `POST /api/upload/pdf` - Upload a PDF file

### Process

- `POST /api/process/pdf?file_id={file_id}` - Start processing a PDF
- `GET /api/process/status/{job_id}` - Check processing job status
- `GET /api/process/receipts/{file_id}` - Get extracted receipts

### Export

- `GET /api/export/csv?file_id={file_id}` - Export receipts as CSV
- `GET /api/export/excel?file_id={file_id}` - Export receipts as Excel

## Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration settings
├── database.py            # Database connection and session
├── routers/
│   ├── upload.py          # File upload endpoints
│   ├── process.py          # Processing endpoints
│   └── export.py           # Export endpoints
├── services/
│   ├── pdf_utils.py       # PDF to image conversion
│   ├── receipt_detector.py # YOLO receipt detection (placeholder)
│   ├── ocr_engine.py      # OCR text extraction (placeholder)
│   ├── llm_extractor.py   # Ollama LLM field extraction
│   └── pipeline.py        # End-to-end processing pipeline
├── models/
│   ├── receipt.py         # Pydantic schemas
│   └── db_models.py       # SQLAlchemy models
├── utils/
│   ├── file_manager.py    # File management utilities
│   └── responses.py       # Standard API responses
├── temp/                  # Temporary file storage
└── exports/               # Exported CSV/Excel files
```

## Placeholder Implementations

### YOLO Receipt Detection

The `receipt_detector.py` module currently returns the entire image as a single receipt. To implement actual YOLO detection:

1. Install YOLO dependencies:
```bash
pip install ultralytics torch torchvision
```

2. Train or download a YOLO model for receipt detection
3. Update `detect_receipts()` in `services/receipt_detector.py`

### PaddleOCR

The `ocr_engine.py` module currently returns placeholder text. To implement actual OCR:

1. Install PaddleOCR:
```bash
pip install paddlepaddle paddleocr
```

2. Update `run_ocr()` in `services/ocr_engine.py`

## Usage Example

```python
import requests

# 1. Upload PDF
with open("receipts.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/upload/pdf",
        files={"file": f}
    )
file_id = response.json()["data"]["file_id"]

# 2. Process PDF
response = requests.post(
    f"http://localhost:8000/api/process/pdf",
    params={"file_id": file_id}
)
job_id = response.json()["data"]["job_id"]

# 3. Check status
response = requests.get(
    f"http://localhost:8000/api/process/status/{job_id}"
)
status = response.json()["data"]["status"]

# 4. Get receipts
response = requests.get(
    f"http://localhost:8000/api/process/receipts/{file_id}"
)
receipts = response.json()["data"]["receipts"]

# 5. Export to CSV
response = requests.get(
    f"http://localhost:8000/api/export/csv",
    params={"file_id": file_id}
)
with open("receipts.csv", "wb") as f:
    f.write(response.content)
```

## Development Notes

- The backend uses background tasks for long-running PDF processing
- Job status is tracked in-memory (consider Redis for production)
- Temporary files are stored in `backend/temp/`
- Exported files are stored in `backend/exports/`
- Database tables are automatically created on startup

## Production Considerations

1. Use Redis or a proper job queue (Celery) for background tasks
2. Implement proper file cleanup for temporary files
3. Add authentication and authorization
4. Configure CORS properly for your frontend domain
5. Use environment variables for all sensitive configuration
6. Set up proper logging
7. Add rate limiting
8. Implement proper error handling and retries

