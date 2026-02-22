## Receipt Genie – Multi‑VAT Receipt Scanner

Receipt Genie is an end‑to‑end system for turning receipt PDFs/images into clean, structured data with **OCR + LLM extraction**, **multi‑VAT support**, and an **editable table UI** that can be exported to CSV/Excel.

- **Input**: PDF or single images (one or multiple receipts per page)
- **Processing**: PDF → images → receipt detection → OCR → LLM field extraction → VAT reconciliation/validation
- **Output**: Receipts table (frontend), CSV, Excel

The stack:

- **Frontend**: Vite, React, TypeScript, Tailwind CSS, shadcn‑ui
- **Backend**: FastAPI, SQLAlchemy, SQLite/MySQL, Pandas
- **AI/OCR**: PaddleOCR (or configured OCR engine) + local LLM via Ollama

---

## 1. Getting Started

### Requirements

- Python 3.10+
- Node.js 18+ and npm
- [Ollama](https://ollama.com) running locally with a suitable model (configured in `backend/config.py` / `.env`)

### Clone and install

```bash
git clone <YOUR_GIT_URL>
cd receipt-genie

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../
npm install
```

### Environment configuration

In `backend/.env` (or `backend/config.py`) configure at least:

- `DATABASE_URL` – e.g. `sqlite:///./receipt_scanner.db`
- `OLLAMA_BASE_URL` – usually `http://localhost:11434`
- `OLLAMA_MODEL` – e.g. `llama3.2` or another extraction‑capable model

---

## 2. Running the App

### Backend (FastAPI)

From `backend/`:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

This will:

- Create/update database tables
- Expose the API at `http://localhost:8000`
- Serve:
  - `/api/upload/file` – upload PDFs or images
  - `/api/process/pdf` – start processing
  - `/api/process/receipts/{file_id}` – get receipts
  - `/api/process/receipt/{id}` – PATCH edited receipt
  - `/api/export/csv?file_id=...`
  - `/api/export/excel?file_id=...`

### Frontend (React)

From the project root:

```bash
npm run dev
```

Open the URL shown in the console (typically `http://localhost:5173`).

Set `VITE_API_URL` in a `.env` file in the project root if your backend is not on the default `http://localhost:8000`.

---

## 3. Workflow in the UI

1. **Upload**
   - Click “Upload” and select a PDF or image.
   - Status bar shows upload and processing progress.

2. **Process**
   - Click “Process Receipts”.
   - Pipeline runs:
     - PDF → images
     - Receipt detection (handles multiple receipts per page; falls back to full page when needed)
     - OCR
     - LLM extraction
     - VAT reconciliation (see below)

3. **Review & Edit**
   - Results appear in an **editable table**:
     - Store name, date, total, VAT amount, VAT %, currency, accuracy.
   - Click the pencil icon in a cell to edit.
   - Edits are persisted via `PATCH /api/process/receipt/{id}`.
   - “Save All Changes” will batch‑save any pending edits.

4. **Export (Edited Data)**
   - Use the **Download CSV** / **Download Excel** buttons.
   - Exports always use the **current database state**, so any saved edits are reflected.
   - CSV/Excel columns include:
     - Store Name, Date, Subtotal, VAT Amount, VAT %, VAT Breakdown, Total Amount, Currency, Payment Method, Items, Address, Phone, Confidence, Extraction Date.

> Make sure edits are saved (no “unsaved changes” banner) before exporting, so the file reflects the edited values.

---

## 4. VAT / Tax Handling

The backend contains a VAT reconciliation step in `backend/services/llm_extractor.py`:

- Supports **multiple VAT rates per receipt** (e.g. 9% + 21%).
- Supports **per‑item VAT** (`vat_rate` per line).
- Builds a `vat_breakdown` array:
  - `[{ vat_rate, base_amount, tax_amount }, ...]`
- Computes a **weighted effective VAT** (`vat_percentage_effective`).
- **Validates and normalizes**:
  - Snaps noisy rates to common NL rates: `0, 9, 10, 21`.
  - Rejects unrealistic rates (>30%).
  - Ensures `tax_amount ≈ base_amount * rate / 100` within a small tolerance.
  - For single‑rate receipts, recomputes base/tax so `subtotal + VAT = total`.

Warnings from this validator are stored server‑side and can be surfaced in the UI to flag suspicious receipts.

---

## 5. Project Structure (High‑Level)

- `backend/`
  - `main.py` – FastAPI app entrypoint
  - `services/`
    - `pipeline.py` – end‑to‑end PDF → receipts pipeline
    - `receipt_detector.py` – classical CV receipt detection & cropping
    - `ocr_engine.py` – OCR abstraction
    - `llm_extractor.py` – LLM prompt + JSON parsing + VAT reconciliation
  - `models/`
    - `db_models.py` – SQLAlchemy models (`UploadedFile`, `Receipt`, `ProcessingJob`)
    - `receipt.py` – Pydantic schemas
  - `routers/`
    - `upload.py`, `process.py`, `export.py`
  - `temp/` – working directory for images and crops

- `src/`
  - `components/receipt-scanner/` – main scanner UI, editable table, export buttons
  - `services/api.ts` – frontend API client
  - `types/receipt.ts` – frontend receipt types

---

## 6. Testing & Debugging

- **Backend tests** (where present):

```bash
cd backend
pytest
```

- To debug detection on a specific PDF/image:
  - Use `backend/test_receipt_detector.py` (see `backend/docs/TESTING_RECEIPT_DETECTOR.md`).
  - Inspect cropped images under `backend/temp/crops/`.

---

## 7. Notes & Limitations

- OCR and LLM quality depend on image quality and the model you use in Ollama.
- VAT logic is tuned for **Dutch receipts** (9% / 21% plus some 10% cases); other countries may need adjustments.
- For production, you’ll likely want a persistent database (MySQL/PostgreSQL) instead of SQLite and a hardened deployment (systemd, Docker, etc.).
