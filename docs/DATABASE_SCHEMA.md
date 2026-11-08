# Database schema

```mermaid
erDiagram
    DOCUMENTS ||--o{ VALIDATION_ISSUES : has
    DOCUMENTS ||--o{ PROCESSING_EVENTS : records
    DOCUMENTS ||--o{ CORRECTIONS : audits
    DOCUMENTS ||--o| INVOICE_REGISTRY : identifies

    DOCUMENTS {
      uuid id PK
      string original_name
      string stored_name UK
      string checksum_sha256
      enum status
      int progress
      int page_count
      text raw_text
      json structured_data
      json confidence
      json embedding
      bool needs_review
      text error_message
      datetime created_at
      datetime completed_at
    }
    VALIDATION_ISSUES {
      int id PK
      uuid document_id FK
      string code
      string field
      string severity
      text message
      string expected
      string actual
    }
    PROCESSING_EVENTS {
      int id PK
      uuid document_id FK
      string stage
      string status
      int duration_ms
      datetime created_at
    }
    CORRECTIONS {
      int id PK
      uuid document_id FK
      string field
      json old_value
      json new_value
      string corrected_by
      datetime created_at
    }
    INVOICE_REGISTRY {
      int id PK
      uuid document_id FK
      string invoice_number
      string supplier_normalized
    }
```

`(invoice_number, supplier_normalized)` is unique for durable duplicate detection. Structured results remain JSON for evolution; operational filters use first-class columns. For production vector search, migrate `embedding` from JSON to `vector(n)` with a pgvector HNSW index.

