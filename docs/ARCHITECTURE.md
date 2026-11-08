# Architecture

```mermaid
flowchart LR
    U[Reviewer / API client] --> UI[React review workspace]
    UI --> API[FastAPI REST API]
    API --> FS[(Encrypted object storage\nLocal volume in development)]
    API --> DB[(PostgreSQL\nSQLite fallback)]
    API --> Q[Redis queue]
    Q --> W[Celery workers]
    W --> P{File router}
    P --> PDF[Digital PDF reader]
    P --> OCR[PDF/image OCR\nTesseract]
    P --> TAB[Excel/CSV parser\npandas + openpyxl]
    PDF --> X[Extraction service]
    OCR --> X
    TAB --> X
    X --> LLM[Optional OpenAI\nStructured Outputs]
    X --> RULE[Deterministic fallback]
    LLM --> V[Validation engine]
    RULE --> V
    V --> DB
    DB --> S[Keyword + semantic search]
    S --> API
```

## Processing state machine

```mermaid
stateDiagram-v2
    [*] --> queued: accepted
    queued --> processing: worker starts
    processing --> completed: extraction valid
    processing --> needs_review: validation issues
    processing --> failed: safe exception
    failed --> queued: reprocess
    needs_review --> completed: corrected and valid
    completed --> queued: explicit reprocess
```

The API never performs long OCR synchronously when Celery mode is enabled. Development mode uses FastAPI background tasks to minimize setup. A stage event is written at upload, parse, extract, validate, and failure boundaries.

For 1000-page PDFs, the current worker extracts/rasterizes sequentially. A production evolution can fan out page ranges into child jobs, merge text in page order, and apply backpressure per tenant.

