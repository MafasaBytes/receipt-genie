# Backend Testing Guide

This guide helps you test the Receipt Scanner backend with actual data.

## Prerequisites

1. **Backend server running**: `python main.py`
2. **Ollama running** (for LLM extraction): `ollama serve`
3. **Ollama model installed**: `ollama pull llama3.2` (or your preferred model)
4. **Test PDF file** with receipts

## Quick Test

### 1. Start the Backend

```bash
cd backend
python main.py
```

You should see:
```
✓ Database tables created successfully
✓ Ollama is running and accessible
🚀 Receipt Scanner API is ready!
```

### 2. Test with Python Script

```bash
python test_backend.py
```

This interactive script will:
- Test health endpoint
- Upload your PDF
- Process it
- Monitor job status
- Fetch extracted receipts
- Export to CSV/Excel

### 3. Manual Testing with curl

#### Upload PDF
```bash
curl -X POST -F "file=@your_receipts.pdf" http://localhost:8000/api/upload/pdf
```

Response:
```json
{
  "file_id": "uuid-here",
  "filename": "your_receipts.pdf",
  "file_size": 12345,
  "message": "File uploaded successfully"
}
```

#### Process PDF
```bash
curl -X POST "http://localhost:8000/api/process/pdf?file_id=YOUR_FILE_ID"
```

Response:
```json
{
  "job_id": "uuid-here",
  "file_id": "uuid-here",
  "status": "pending",
  "message": "Processing started..."
}
```

#### Check Job Status
```bash
curl "http://localhost:8000/api/process/status/YOUR_JOB_ID"
```

#### Get Extracted Receipts
```bash
curl "http://localhost:8000/api/process/receipts/YOUR_FILE_ID"
```

#### Export CSV
```bash
curl "http://localhost:8000/api/export/csv?file_id=YOUR_FILE_ID" -o receipts.csv
```

#### Export Excel
```bash
curl "http://localhost:8000/api/export/excel?file_id=YOUR_FILE_ID" -o receipts.xlsx
```

## Testing with Postman/Thunder Client

1. **Import Collection**: Use the endpoints above
2. **Set Base URL**: `http://localhost:8000/api`
3. **Upload**: Use form-data with key `file` and type `File`

## Testing with Python Requests

See `test_backend.py` for a complete example.

## Performance Monitoring

The backend logs performance metrics:
- PDF to images conversion time
- LLM extraction time per receipt
- Total pipeline time
- Number of receipts extracted

Check the console output for timing information.

## Troubleshooting

### "Ollama is not available"
- Start Ollama: `ollama serve`
- Pull a model: `ollama pull llama3.2`
- Check connection: `curl http://localhost:11434/api/tags`

### "Database connection failed"
- For SQLite: Should work automatically
- For MySQL: See `SETUP_DATABASE.md`

### "Processing failed"
- Check server logs for detailed error messages
- Verify PDF is valid and contains readable receipts
- Ensure Ollama is running and model is available

### "No receipts extracted"
- PDF might not contain receipts
- OCR might not be extracting text properly (placeholder implementation)
- LLM might be failing to parse (check Ollama logs)

## Expected Performance

- **PDF to Images**: ~1-2 seconds per page
- **Receipt Detection**: Instant (placeholder)
- **OCR**: Instant (placeholder - returns sample data)
- **LLM Extraction**: 5-15 seconds per receipt (depends on model)
- **Total**: ~10-20 seconds per receipt

## Next Steps

1. Replace placeholder OCR with actual PaddleOCR
2. Replace placeholder YOLO with actual model
3. Fine-tune LLM prompts for better extraction
4. Add error recovery and retry logic
5. Optimize for batch processing

