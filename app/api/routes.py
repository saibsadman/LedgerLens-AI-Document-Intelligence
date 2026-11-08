from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Correction, Document, DocumentStatus, ProcessingEvent
from app.schemas import (
    CompareRequest,
    CorrectionRequest,
    DocumentDetail,
    DocumentSummary,
    InvoiceExtraction,
    SearchResponse,
    UploadResponse,
)
from app.services.document_processor import SUPPORTED_EXTENSIONS
from app.services.pipeline import process_document, revalidate_document
from app.services.search import cosine_similarity, embed_text

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


def _dispatch(document_id: str, background_tasks: BackgroundTasks) -> None:
    if settings.use_celery:
        from app.worker import process_document_task

        process_document_task.delay(document_id)
    else:
        background_tasks.add_task(process_document, document_id)


async def _save_upload(upload: UploadFile) -> tuple[str, int, str]:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{extension or 'unknown'}'")
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = settings.storage_path / stored_name
    size = 0
    digest = hashlib.sha256()
    try:
        with destination.open("xb") as target:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise ValueError("File is empty")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return stored_name, size, digest.hexdigest()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.post(
    "/documents/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    db: DbSession,
    files: Annotated[list[UploadFile], File(description="PDF, image, Excel, or CSV documents")],
) -> UploadResponse:
    if not files:
        raise HTTPException(400, "At least one file is required")
    accepted: list[Document] = []
    rejected: list[dict[str, str]] = []
    for upload in files:
        original_name = Path(upload.filename or "unnamed").name[:255]
        try:
            stored_name, size, checksum = await _save_upload(upload)
            document = Document(
                original_name=original_name,
                stored_name=stored_name,
                mime_type=upload.content_type,
                extension=Path(stored_name).suffix.lower(),
                size_bytes=size,
                checksum_sha256=checksum,
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            db.add(
                ProcessingEvent(
                    document_id=document.id,
                    stage="upload",
                    status="completed",
                    message=f"{size} bytes",
                )
            )
            db.commit()
            accepted.append(document)
            _dispatch(document.id, background_tasks)
        except Exception as exc:
            db.rollback()
            rejected.append({"filename": original_name, "reason": str(exc)})
    return UploadResponse(
        accepted=[DocumentSummary.model_validate(item) for item in accepted], rejected=rejected
    )


@router.get("/documents", response_model=SearchResponse)
def list_documents(
    db: DbSession,
    q: str | None = None,
    status_filter: DocumentStatus | None = Query(None, alias="status"),
    needs_review: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    conditions = []
    if q:
        needle = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(Document.original_name).like(needle),
                func.lower(Document.raw_text).like(needle),
                func.lower(cast(Document.structured_data, String)).like(needle),
            )
        )
    if status_filter:
        conditions.append(Document.status == status_filter)
    if needs_review is not None:
        conditions.append(Document.needs_review == needs_review)
    base = select(Document).where(*conditions)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    documents = db.scalars(
        base.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return SearchResponse(
        items=[DocumentSummary.model_validate(item) for item in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: DbSession) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.get("/documents/{document_id}/status", response_model=DocumentSummary)
def get_processing_status(document_id: str, db: DbSession) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    return document


@router.post("/documents/{document_id}/reprocess", response_model=DocumentSummary, status_code=202)
def reprocess_document(
    document_id: str, background_tasks: BackgroundTasks, db: DbSession
) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    if document.status == DocumentStatus.processing:
        raise HTTPException(409, "Document is already being processed")
    document.status = DocumentStatus.queued
    document.progress = 0
    document.error_message = None
    db.commit()
    _dispatch(document.id, background_tasks)
    return document


@router.patch("/documents/{document_id}", response_model=DocumentDetail)
def correct_document(document_id: str, request: CorrectionRequest, db: DbSession) -> Document:
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(404, "Document not found")
    allowed = {
        "invoice_number",
        "invoice_date",
        "supplier_name",
        "customer_name",
        "subtotal",
        "tax",
        "total",
        "currency",
        "line_items",
    }
    invalid = set(request.updates) - allowed
    if invalid:
        raise HTTPException(422, f"Unsupported correction fields: {', '.join(sorted(invalid))}")
    data: dict[str, Any] = dict(document.structured_data or {})
    candidate = {**data, **request.updates}
    try:
        validated = InvoiceExtraction.model_validate(candidate)
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors(include_url=False)) from exc
    for field, new_value in request.updates.items():
        db.add(
            Correction(
                document_id=document.id,
                field=field,
                old_value=data.get(field),
                new_value=new_value,
                corrected_by=request.corrected_by,
            )
        )
    document.structured_data = validated.model_dump(mode="json")
    db.commit()
    revalidate_document(db, document)
    db.refresh(document)
    return document


@router.get("/search/semantic", response_model=list[DocumentSummary])
def semantic_search(
    db: DbSession, q: str = Query(min_length=2), limit: int = Query(10, ge=1, le=50)
) -> list[DocumentSummary]:
    query_vector = embed_text(q)
    candidates = db.scalars(
        select(Document)
        .where(Document.embedding.is_not(None))
        .order_by(Document.created_at.desc())
        .limit(1000)
    ).all()
    ranked = sorted(
        candidates, key=lambda item: cosine_similarity(item.embedding, query_vector), reverse=True
    )[:limit]
    return [DocumentSummary.model_validate(item) for item in ranked]


@router.post("/documents/compare")
def compare_documents(request: CompareRequest, db: DbSession) -> dict[str, Any]:
    left = db.get(Document, request.left_document_id)
    right = db.get(Document, request.right_document_id)
    if not left or not right:
        raise HTTPException(404, "One or both documents were not found")
    fields = request.fields or [
        "invoice_number",
        "invoice_date",
        "supplier_name",
        "customer_name",
        "subtotal",
        "tax",
        "total",
        "currency",
    ]
    left_data = left.structured_data or {}
    right_data = right.structured_data or {}
    comparisons = []
    for field in fields:
        left_value, right_value = left_data.get(field), right_data.get(field)
        comparisons.append(
            {
                "field": field,
                "left": left_value,
                "right": right_value,
                "matches": left_value == right_value and left_value is not None,
            }
        )
    return {
        "left_document_id": left.id,
        "right_document_id": right.id,
        "matches": all(item["matches"] for item in comparisons),
        "comparisons": comparisons,
    }


@router.get("/documents/{document_id}/history")
def processing_history(document_id: str, db: DbSession) -> list[dict[str, Any]]:
    if not db.get(Document, document_id):
        raise HTTPException(404, "Document not found")
    events = db.scalars(
        select(ProcessingEvent)
        .where(ProcessingEvent.document_id == document_id)
        .order_by(ProcessingEvent.created_at)
    ).all()
    return [
        {
            "stage": event.stage,
            "status": event.status,
            "message": event.message,
            "duration_ms": event.duration_ms,
            "created_at": event.created_at,
        }
        for event in events
    ]
