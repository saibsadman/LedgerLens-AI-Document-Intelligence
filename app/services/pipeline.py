from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Document, DocumentStatus, InvoiceRegistry, ProcessingEvent, ValidationIssue
from app.schemas import InvoiceExtraction
from app.services.document_processor import process_file
from app.services.extraction import extract_invoice
from app.services.search import embed_text
from app.services.validation import validate_invoice


def _event(
    db,
    document_id: str,
    stage: str,
    status: str,
    message: str | None = None,
    duration_ms: int | None = None,
) -> None:
    db.add(
        ProcessingEvent(
            document_id=document_id,
            stage=stage,
            status=status,
            message=message,
            duration_ms=duration_ms,
        )
    )
    db.commit()


def _normalize_supplier(value: str) -> str:
    return " ".join(value.lower().split())


def process_document(document_id: str) -> None:
    db = SessionLocal()
    document = db.get(Document, document_id)
    if not document:
        db.close()
        return
    document.status = DocumentStatus.processing
    document.progress = 5
    document.error_message = None
    db.commit()
    try:
        started = time.perf_counter()
        _event(db, document.id, "parse", "started")
        parsed = process_file(settings.storage_path / document.stored_name)
        document.raw_text = parsed.text
        document.page_count = parsed.page_count
        document.progress = 42
        db.commit()
        _event(
            db,
            document.id,
            "parse",
            "completed",
            f"OCR used: {parsed.used_ocr}",
            int((time.perf_counter() - started) * 1000),
        )

        started = time.perf_counter()
        _event(db, document.id, "extract", "started")
        invoice = extract_invoice(parsed.text)
        document.structured_data = invoice.model_dump(mode="json")
        document.confidence = invoice.field_confidence
        document.progress = 70
        db.commit()
        _event(
            db,
            document.id,
            "extract",
            "completed",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

        db.query(ValidationIssue).filter(ValidationIssue.document_id == document.id).delete()

        def duplicate_check(number: str, supplier: str) -> bool:
            statement = select(InvoiceRegistry.id).where(
                InvoiceRegistry.invoice_number == number,
                InvoiceRegistry.supplier_normalized == _normalize_supplier(supplier),
                InvoiceRegistry.document_id != document.id,
            )
            return db.scalar(statement) is not None

        issues = validate_invoice(invoice, duplicate_check)
        for issue in issues:
            db.add(ValidationIssue(document_id=document.id, **issue.__dict__))

        registry = db.scalar(
            select(InvoiceRegistry).where(InvoiceRegistry.document_id == document.id)
        )
        if invoice.invoice_number and invoice.supplier_name:
            if registry is None and not duplicate_check(
                invoice.invoice_number, invoice.supplier_name
            ):
                db.add(
                    InvoiceRegistry(
                        document_id=document.id,
                        invoice_number=invoice.invoice_number,
                        supplier_normalized=_normalize_supplier(invoice.supplier_name),
                    )
                )
            elif registry is not None:
                registry.invoice_number = invoice.invoice_number
                registry.supplier_normalized = _normalize_supplier(invoice.supplier_name)

        document.embedding = embed_text(parsed.text[:100_000])
        document.needs_review = bool(issues)
        document.status = DocumentStatus.needs_review if issues else DocumentStatus.completed
        document.progress = 100
        document.completed_at = datetime.now(timezone.utc)
        db.commit()
        _event(db, document.id, "validate", "completed", f"{len(issues)} issue(s)")
    except Exception as exc:
        db.rollback()
        document = db.get(Document, document_id)
        if document:
            document.status = DocumentStatus.failed
            document.error_message = str(exc)[:2000]
            document.progress = 100
            db.commit()
            _event(db, document.id, "pipeline", "failed", document.error_message)
    finally:
        db.close()


def revalidate_document(db, document: Document) -> list[ValidationIssue]:
    db.query(ValidationIssue).filter(ValidationIssue.document_id == document.id).delete()
    invoice = InvoiceExtraction.model_validate(document.structured_data or {})
    issues = validate_invoice(invoice)
    records = [ValidationIssue(document_id=document.id, **issue.__dict__) for issue in issues]
    db.add_all(records)
    document.needs_review = bool(issues)
    document.status = DocumentStatus.needs_review if issues else DocumentStatus.completed
    db.commit()
    return records
