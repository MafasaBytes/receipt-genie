# Troubleshooting: Pipeline Not Returning Results

## Issue
The detector works when tested directly, but the full pipeline returns no results.

## Enhanced Debugging

### 1. Check Server Logs

The pipeline now has detailed logging. Check the server console output for:
- Detection results
- OCR text length
- LLM extraction status
- Any error messages

### 2. Use Debug Script

Run the debug script to see detailed pipeline execution:

```bash
# First, upload a PDF and get the file_id
curl -X POST -F "file=@your_file.pdf" http://localhost:8000/api/upload/pdf

# Then debug with the file_id
python debug_pipeline.py YOUR_FILE_ID
```

This will show:
- Each step of the pipeline
- Detection results
- OCR output
- LLM extraction results
- Any errors with full tracebacks

### 3. Common Issues and Solutions

#### Issue: Detector finds receipts but pipeline returns nothing

**Possible causes:**
1. **OCR placeholder returns insufficient text**
   - Check logs for "Insufficient OCR text extracted"
   - The placeholder should return enough text, but verify

2. **LLM extraction failing**
   - Check if Ollama is running: `curl http://localhost:11434/api/tags`
   - Check logs for LLM errors
   - The pipeline now continues with empty fields if LLM fails

3. **Database save failing**
   - Check database connection
   - Verify database tables exist
   - Check logs for database errors

4. **Path issues**
   - Cropped images might not exist when OCR tries to read them
   - Check logs for "Cropped receipt image not found"

#### Issue: No receipts detected

**Check:**
- Are cropped images being created? Check `temp/{file_id}_images/`
- Does the detector return paths? Check logs
- Is the fallback working? Should return original image path

#### Issue: Processing completes but 0 receipts

**Check logs for:**
- "Insufficient OCR text extracted" - OCR might be failing
- "LLM extraction failed" - Ollama might not be running
- "Error processing receipt" - Check full error traceback

## Enhanced Error Handling

The pipeline now:
- ✅ Logs all detection results
- ✅ Verifies cropped images exist before processing
- ✅ Continues with empty fields if LLM fails (instead of failing completely)
- ✅ Provides detailed error messages with tracebacks
- ✅ Shows progress at each step

## Testing Steps

1. **Test detector directly:**
   ```bash
   python test_receipt_detector.py
   ```
   Verify detection works and creates cropped images.

2. **Test full pipeline with debug:**
   ```bash
   python debug_pipeline.py YOUR_FILE_ID
   ```
   This shows exactly where the pipeline is failing.

3. **Check server logs:**
   When running via API, check the server console for detailed logs.

4. **Verify each step:**
   - Detection: Are cropped images created?
   - OCR: Is text extracted? (Check logs for text length)
   - LLM: Is Ollama running? Are fields extracted?
   - Database: Are receipts saved?

## Log Levels

The pipeline uses these log levels:
- **INFO**: Normal progress messages
- **WARNING**: Non-fatal issues (fallbacks, insufficient text)
- **ERROR**: Failures that are handled gracefully
- **DEBUG**: Detailed information (text previews, path details)

To see DEBUG logs, set logging level:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

If the pipeline still returns nothing after checking logs:

1. Run `debug_pipeline.py` with your file_id
2. Share the output - it will show exactly where it's failing
3. Check if cropped images exist in temp directory
4. Verify Ollama is running if LLM extraction is needed
5. Check database connection and tables

