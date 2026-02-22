## Receipt Genie -- Multi-VAT Receipt Scanner with RAG

Receipt Genie is an end-to-end system for turning receipt PDFs/images into clean, structured data with **OCR + RAG-LLM extraction**, **Dutch multi-rate VAT intelligence**, and an **editable table UI** that can be exported to CSV/Excel.

- **Input**: PDF or single images (one or multiple receipts per page)
- **Processing**: PDF text extraction (langchain) / image OCR -> RAG context retrieval -> LLM field extraction -> VAT reconciliation
- **Output**: Receipts table with per-item descriptions, CSV, Excel

The stack:

- **Frontend**: Vite, React, TypeScript, Tailwind CSS, shadcn-ui
- **Backend**: FastAPI, SQLAlchemy, SQLite/MySQL, Pandas
- **AI/OCR**: PaddleOCR + local LLM via Ollama + RAG (ChromaDB + nomic-embed-text)

---

## 1. Getting Started

### Requirements

- Python 3.10+
- Node.js 18+ and npm
- [Ollama](https://ollama.com) running locally with:
  - A generative model (e.g. `llama3.2`) for receipt extraction
  - An embedding model (`nomic-embed-text`) for the RAG pipeline

Pull the required Ollama models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

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

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./receipt_scanner.db` | Database connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:latest` | Generative model for extraction |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model for RAG |
| `RAG_ENABLED` | `True` | Toggle RAG pipeline on/off |
| `RAG_TOP_K` | `3` | Number of similar receipts to retrieve |
| `RAG_MIN_SIMILARITY` | `0.55` | Minimum cosine similarity threshold |

---

## 2. Running the App

### Backend (FastAPI)

From the project root:

```bash
python backend/main.py
```

This will:

- Create/update database tables
- Verify the Ollama connection and embedding model availability
- Initialize the ChromaDB vector store (persisted in `backend/vector_store/`)
- Expose the API at `http://localhost:8000`
- Serve:
  - `POST /api/upload/file` -- upload PDFs or images
  - `POST /api/process/pdf` -- start processing
  - `GET  /api/process/status/{job_id}` -- poll job status
  - `GET  /api/process/receipts/{file_id}` -- get extracted receipts
  - `PATCH /api/process/receipt/{id}` -- update edited receipt
  - `GET  /api/process/rag/stats` -- RAG vector store statistics
  - `GET  /api/export/csv?file_id=...`
  - `GET  /api/export/excel?file_id=...`

### Frontend (React)

From the project root:

```bash
npm run dev
```

Open the URL shown in the console (typically `http://localhost:5173`).

Set `VITE_API_URL` in a `.env` file in the project root if your backend is not on the default `http://localhost:8000`.

---

## 3. Workflow in the UI

1. **Upload** -- Click "Upload" and select a PDF or image. Status bar shows upload and processing progress.

2. **Process** -- Click "Process Receipts". The pipeline runs:
   - For **PDFs**: text extraction via langchain (falls back to image OCR for scanned pages)
   - For **images**: full-image OCR via PaddleOCR
   - RAG context retrieval (similar past receipts as few-shot examples)
   - LLM extraction with Dutch VAT-aware item-level prompting
   - VAT reconciliation and validation

3. **Review & Edit** -- Results appear in an editable table:
   - **Store Name** -- merchant/shop name
   - **Description** -- per-item breakdown with VAT rates (e.g. "Coffee (9%) 4.50, USB Cable (21%) 12.99")
   - **Date**, **Total**, **VAT**, **VAT %**, **Currency**, **Accuracy**
   - Click the pencil icon in a cell to edit. Edits are persisted via `PATCH /api/process/receipt/{id}`.
   - "Save All Changes" will batch-save any pending edits.

4. **Export** -- Use the **Download CSV** / **Download Excel** buttons. Exports always use the current database state, so any saved edits are reflected.

---

## 4. RAG Pipeline

The system uses **Retrieval-Augmented Generation** to improve extraction accuracy over time:

1. **Embedding**: OCR text from each receipt is embedded using `nomic-embed-text` via the Ollama embedding API.
2. **Storage**: Embeddings are stored in a ChromaDB persistent vector store (`backend/vector_store/`).
3. **Retrieval**: When processing a new receipt, the system queries ChromaDB for the top-K most similar past receipts.
4. **Few-shot injection**: Retrieved examples are formatted as reference output and injected into the LLM prompt, giving the model concrete examples of correct extraction for similar receipts.
5. **Indexing**: After successful extraction, the new receipt is indexed back into the vector store, continually improving future results.

RAG can be toggled off via `RAG_ENABLED=False` in the configuration.

---

## 5. VAT / Tax Handling

### Dutch Multi-Rate VAT Intelligence

The LLM prompt includes explicit Dutch VAT guidance:

| Rate | Category |
|------|----------|
| 21%  | Standard: electronics, clothing, services, non-food |
| 9%   | Reduced: food, drinks, medicines, books, newspapers, hotels |
| 0%   | Exempt: education, healthcare, certain financial services |

The system:

- Extracts **every individual line item** with per-item `name`, `quantity`, `unit_price`, `line_total`, and `vat_rate`
- Maps receipt VAT indicator codes (e.g. "A"=21%, "B"=9%) to numeric rates
- Assigns the correct VAT rate per item based on product category
- Builds a `vat_breakdown` array: `[{ vat_rate, base_amount, tax_amount }, ...]`
- Computes a **weighted effective VAT** (`vat_percentage_effective`)
- **Validates and normalizes**: snaps noisy rates to common NL rates, rejects unrealistic rates (>30%), ensures internal consistency

---

## 6. Project Structure

```
receipt-genie/
├── backend/
│   ├── main.py                    # FastAPI app entrypoint + startup logic
│   ├── config.py                  # Centralized settings (Ollama, RAG, DB, etc.)
│   ├── database.py                # SQLAlchemy engine + session
│   ├── requirements.txt
│   ├── prompts/
│   │   └── receipt_extraction.yml # LLM prompt with item extraction + Dutch VAT rules
│   ├── services/
│   │   ├── pipeline.py            # End-to-end PDF/image -> receipts pipeline
│   │   ├── pdf_text_extractor.py  # PDF text extraction via langchain-community
│   │   ├── ocr_engine.py          # PaddleOCR abstraction
│   │   ├── llm_extractor.py       # LLM prompt building, JSON parsing, VAT reconciliation
│   │   ├── embedding_service.py   # Ollama embedding API client
│   │   ├── vector_store.py        # ChromaDB vector store abstraction
│   │   ├── rag_service.py         # RAG orchestration (retrieve, format, cross-validate)
│   │   ├── receipt_detector.py    # Classical CV receipt detection (legacy, not used for PDFs)
│   │   └── pdf_utils.py           # PDF-to-image conversion utilities
│   ├── models/
│   │   ├── db_models.py           # SQLAlchemy models (UploadedFile, Receipt, ProcessingJob)
│   │   └── receipt.py             # Pydantic schemas
│   ├── routers/
│   │   ├── upload.py              # File upload endpoints
│   │   ├── process.py             # Processing, status, receipts endpoints
│   │   └── export.py              # CSV/Excel export endpoints
│   ├── temp/                      # Working directory for images
│   └── vector_store/              # ChromaDB persistence (gitignored)
│
├── src/
│   ├── components/receipt-scanner/
│   │   ├── ReceiptScanner.tsx     # Main scanner UI orchestrator
│   │   ├── EditableReceiptTable.tsx # Editable results table with Description column
│   │   └── ReceiptsTable.tsx      # Read-only results table with Description column
│   ├── services/
│   │   └── api.ts                 # Frontend API client + backend-to-frontend mapping
│   └── types/
│       └── receipt.ts             # TypeScript receipt/item/VAT types
│
├── package.json
├── vite.config.ts
└── README.md
```

---

## 7. Testing & Debugging

- **Backend tests** (where present):

```bash
cd backend
pytest
```

- Check Ollama connectivity: `curl http://localhost:11434/api/tags`
- Check RAG stats: `curl http://localhost:8000/api/process/rag/stats`
- Backend logs show detailed pipeline stages: PDF text extraction, OCR, RAG retrieval, LLM prompt/response, JSON parsing, and VAT reconciliation.

---

## 8. Notes & Limitations

- OCR and LLM quality depend on image quality and the model you use in Ollama.
- VAT logic is tuned for **Dutch receipts** (9% / 21%); other countries may need prompt adjustments.
- The RAG pipeline improves over time as more receipts are processed and indexed.
- For production, consider a persistent database (MySQL/PostgreSQL) instead of SQLite and a hardened deployment (Docker, etc.).
- The ChromaDB telemetry errors in logs (`posthog - ERROR`) are harmless and suppressed at startup.
