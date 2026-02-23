# Frontend-Backend Integration Guide

## ✅ Integration Complete

The frontend is now fully integrated with the FastAPI backend. Here's what was changed:

### Changes Made

1. **API Service (`src/services/api.ts`)**
   - ✅ Replaced mock data with real backend API calls
   - ✅ `uploadPdf()` now uploads to `/api/upload/pdf`
   - ✅ `processPdf()` now:
     - Starts processing via `/api/process/pdf`
     - Polls job status via `/api/process/status/{job_id}`
     - Fetches receipts via `/api/process/receipts/{file_id}`
   - ✅ `downloadCsv()` and `downloadExcel()` now use backend endpoints
   - ✅ Added receipt mapping from backend format to frontend format

2. **Receipt Type (`src/types/receipt.ts`)**
   - ✅ Added `confidence_score` field for accuracy tracking

3. **Receipts Table (`src/components/receipt-scanner/ReceiptsTable.tsx`)**
   - ✅ Added "Accuracy" column showing confidence score
   - ✅ Color-coded accuracy indicators:
     - Green: ≥80% confidence
     - Yellow: 60-79% confidence
     - Red: <60% confidence

4. **Export Buttons (`src/components/receipt-scanner/ExportButtons.tsx`)**
   - ✅ Updated to use `file_id` instead of receipts array
   - ✅ Calls backend export endpoints

5. **Receipt Scanner (`src/components/receipt-scanner/ReceiptScanner.tsx`)**
   - ✅ Passes `file_id` to ExportButtons component

### API Endpoints Used

- `POST /api/upload/pdf` - Upload PDF file
- `POST /api/process/pdf?file_id={file_id}` - Start processing
- `GET /api/process/status/{job_id}` - Check job progress
- `GET /api/process/receipts/{file_id}` - Get extracted receipts
- `GET /api/export/csv?file_id={file_id}` - Download CSV
- `GET /api/export/excel?file_id={file_id}` - Download Excel

### Configuration

The frontend uses the `VITE_API_URL` environment variable (defaults to `http://localhost:8000`).

To configure:
1. Create a `.env` file in the project root
2. Add: `VITE_API_URL=http://localhost:8000`

### Accuracy/Confidence Scores

The backend provides confidence scores for each receipt:
- Currently set to `1.0` (100%) for all receipts
- Future improvements could calculate based on:
  - OCR quality (text length, recognition accuracy)
  - LLM extraction success (number of fields extracted)
  - Receipt detection success (detected vs. fallback)

### Testing the Integration

1. **Start the backend:**
   ```bash
   cd backend
   python main.py
   ```

2. **Start the frontend:**
   ```bash
   npm run dev
   # or
   yarn dev
   ```

3. **Test the flow:**
   - Upload a PDF file
   - Click "Process Receipts"
   - Watch progress updates
   - View extracted receipts with accuracy scores
   - Export to CSV or Excel

### Known Limitations

1. **Currency**: Currently defaults to 'EUR' if not extracted. The LLM prompt has been updated to extract currency, but the database model doesn't store it yet.

2. **Confidence Scores**: Currently hardcoded to 1.0. Could be improved to calculate based on extraction quality.

3. **Error Handling**: Basic error handling is in place. Could be enhanced with retry logic and better error messages.

### Next Steps for Accuracy Improvement

1. **Calculate confidence scores based on:**
   - OCR text quality (length, character recognition rate)
   - Number of fields successfully extracted
   - Receipt detection method (detected vs. fallback)

2. **Add currency extraction:**
   - Add `currency` field to database model
   - Update pipeline to save currency
   - Update response models

3. **Add validation:**
   - Validate extracted dates
   - Validate amounts (check for reasonable values)
   - Cross-validate fields (e.g., subtotal + tax = total)

