from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    sku: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class InvoiceExtraction(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    supplier_name: str | None = None
    customer_name: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    extraction_notes: list[str] = Field(default_factory=list)


class ValidationIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    field: str | None
    severity: str
    message: str
    expected: str | None
    actual: str | None


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_name: str
    extension: str
    size_bytes: int
    status: str
    progress: int
    page_count: int | None
    needs_review: bool
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentSummary):
    mime_type: str | None
    checksum_sha256: str
    raw_text: str | None
    structured_data: dict[str, Any] | None
    confidence: dict[str, float] | None
    error_message: str | None
    completed_at: datetime | None
    validations: list[ValidationIssueOut] = Field(default_factory=list)


class UploadResponse(BaseModel):
    accepted: list[DocumentSummary]
    rejected: list[dict[str, str]]


class CorrectionRequest(BaseModel):
    updates: dict[str, Any]
    corrected_by: str = "reviewer"


class SearchResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int


class CompareRequest(BaseModel):
    left_document_id: str
    right_document_id: str
    fields: list[str] | None = None
