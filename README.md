# LedgerLens — AI Document Intelligence

LedgerLens is a local-first, production-shaped reference implementation for ingesting financial documents, extracting invoice data, validating calculations, cross-checking documents, and reviewing uncertain results in a web interface.

It accepts PDF, JPG, PNG, TIFF, XLSX, XLS, and CSV. Digital PDF text is read directly; text-poor pages are rasterized and sent through Tesseract OCR one page at a time. Spreadsheets are read sheet-by-sheet. Every file runs through structured extraction, validation, indexing, and a durable audit trail.

## What is included

- Multi-file upload with safe generated storage names, size limits, SHA-256 checksums, and corrupt-file isolation
- Digital PDF extraction plus automatic scanned-page OCR; multi-page TIFF support
- Multi-sheet XLSX/XLS and encoding-aware CSV parsing
- Optional OpenAI Structured Outputs extraction with a deterministic, no-key fallback
- Null-safe invoice JSON: invoice number/date, supplier/customer, subtotal/tax/total, currency, line items, confidence, and notes
- Missing-field, negative-value, total, line-item, duplicate, and confidence validation
- Background processing through Celery + Redis in Docker; FastAPI background tasks for zero-infrastructure local development
- Keyword search, deterministic semantic ranking, PDF-to-PDF / PDF-to-spreadsheet comparison, corrections, reprocessing, and history APIs
- Responsive React review dashboard
- Unit/integration tests and a repeatable measured evaluation runner

## Quick start (without Docker)

Prerequisites: Python 3.11+, Node 20+, and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract). OCR is only required for images/scanned PDF pages.

```powershell
cd D:\work\docintel
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd D:\work\docintel\frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API docs are at `http://localhost:8000/docs`.

To use AI extraction, set `OPENAI_API_KEY` in `.env`. When absent, the deterministic extractor remains fully functional. `OPENAI_MODEL` is configurable. The integration uses the current Responses API structured parsing approach documented in the [official OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Docker start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

This starts PostgreSQL, Redis, FastAPI, a Celery worker, and the frontend. Open `http://localhost:5173`.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | local SQLite |
| `REDIS_URL` | Celery broker/result backend | local Redis |
| `USE_CELERY` | dispatch work to Celery | `false` |
| `STORAGE_PATH` | private uploaded-file directory | `./data/uploads` |
| `MAX_UPLOAD_MB` | per-file upload limit | `100` |
| `OPENAI_API_KEY` | enables AI structured extraction | empty |
| `OPENAI_MODEL` | extraction model | `gpt-4.1-mini` |
| `OCR_LANG` | Tesseract languages (install language packs) | `eng` |
| `TESSERACT_CMD` | Windows executable path when not on PATH | empty |
| `API_KEY` | optional API protection through `X-API-Key` | empty |
| `ALLOWED_ORIGINS` | comma-separated browser origins | localhost UI |

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/documents/upload` | batch upload; returns accepted/rejected files |
| `GET` | `/api/v1/documents` | keyword/filter search and pagination |
| `GET` | `/api/v1/documents/{id}` | extraction, source text, and validation result |
| `GET` | `/api/v1/documents/{id}/status` | lightweight progress polling |
| `PATCH` | `/api/v1/documents/{id}` | audited manual corrections and revalidation |
| `POST` | `/api/v1/documents/{id}/reprocess` | retry a failed or completed job |
| `GET` | `/api/v1/documents/{id}/history` | processing-stage history |
| `GET` | `/api/v1/search/semantic?q=...` | semantic-style similarity search |
| `POST` | `/api/v1/documents/compare` | cross-verify extracted fields |

## Tests and evaluation

```powershell
pytest --cov=app --cov-report=term-missing
python evaluation/run_evaluation.py
cd frontend
npm run build
```

The benchmark writes actual measurements to `evaluation/results.json`. See [evaluation methodology](evaluation/README.md) and the [evaluation report](docs/EVALUATION_REPORT.md). A tiny synthetic benchmark is a smoke test, not a production accuracy claim.

## Scale and reliability

- PDF pages are processed sequentially, avoiding a 1000-page image explosion in memory.
- API and workers scale independently; queue concurrency and worker time limits are configurable.
- Each file is isolated. One corrupt upload does not fail a batch.
- PostgreSQL indexes cover status, review queue, checksum, name, and creation time.
- Search candidates are currently ranked in the service for portability. At high volume, store the same vectors in pgvector/OpenSearch and execute top-k in the database.
- For very large deployments, replace the local storage volume with encrypted S3-compatible object storage, use presigned multipart upload, split PDFs into page/chunk jobs, and add dead-letter queues.

## Security checklist

- Files are stored under UUID names; supplied paths are never trusted.
- Extension allowlist, size limit, parser isolation, checksum, restricted CORS, and optional API-key middleware are enabled.
- API keys remain environment variables and are never persisted in extracted data or logs.
- Containers should run behind TLS and authenticated SSO/RBAC in production. Add malware scanning, encrypted object storage, tenant IDs/row-level security, retention policies, audit export, rate limits, and secret management before handling regulated financial data.
- Never expose uploaded originals directly from the static frontend. Review dependencies and run containers as non-root in hardened production images.

## Repository map

```text
app/                    FastAPI, models, jobs, processors, extraction, validation
frontend/               React/Vite review workspace
tests/                  processor, extraction, validation, API, and search tests
evaluation/             repeatable labeled benchmark and measured JSON output
docs/                   architecture, schema, report, prompts, walkthrough
docker-compose.yml      PostgreSQL, Redis, API, worker, UI
```

## Known boundaries

This submission intentionally does not upload to GitHub or deploy. Authentication is a compact API-key baseline rather than a full identity provider. The built-in semantic embedding is deterministic and offline; pgvector/OpenSearch is the recommended production swap. Accuracy on real documents must be measured on an approved, representative labeled dataset before go-live.

