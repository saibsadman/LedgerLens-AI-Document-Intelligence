import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    extension: Mapped[str] = mapped_column(String(12), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.queued, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[dict | None] = mapped_column(JSON)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    validations: Mapped[list["ValidationIssue"]] = relationship(
        cascade="all, delete-orphan", back_populates="document"
    )
    events: Mapped[list["ProcessingEvent"]] = relationship(
        cascade="all, delete-orphan", back_populates="document"
    )
    corrections: Mapped[list["Correction"]] = relationship(
        cascade="all, delete-orphan", back_populates="document"
    )

    __table_args__ = (Index("ix_documents_name_status", "original_name", "status"),)


class ValidationIssue(Base):
    __tablename__ = "validation_issues"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    field: Mapped[str | None] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str | None] = mapped_column(String(255))
    actual: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[Document] = relationship(back_populates="validations")


class ProcessingEvent(Base):
    __tablename__ = "processing_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[Document] = relationship(back_populates="events")


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(80), nullable=False)
    old_value: Mapped[object | None] = mapped_column(JSON)
    new_value: Mapped[object | None] = mapped_column(JSON)
    corrected_by: Mapped[str] = mapped_column(String(120), default="reviewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document: Mapped[Document] = relationship(back_populates="corrections")


class InvoiceRegistry(Base):
    __tablename__ = "invoice_registry"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True
    )
    invoice_number: Mapped[str] = mapped_column(String(160), nullable=False)
    supplier_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("invoice_number", "supplier_normalized", name="uq_invoice_supplier"),
    )
