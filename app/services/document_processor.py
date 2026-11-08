from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pymupdf
import pytesseract
from charset_normalizer import from_bytes
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageSequence
from pypdf import PdfReader

from app.config import settings

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".xlsx", ".xls", ".csv"}


class ProcessingError(Exception):
    """A safe, user-facing processing failure."""


@dataclass
class ParsedDocument:
    text: str
    page_count: int
    used_ocr: bool = False
    sheets: list[str] = field(default_factory=list)


def _prepare_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("L")
    image = ImageOps.autocontrast(image)
    if min(image.size) < 1200:
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return ImageEnhance.Contrast(image).enhance(1.6)


def _ocr(image: Image.Image) -> str:
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    try:
        return pytesseract.image_to_string(
            _prepare_image(image), lang=settings.ocr_lang, config="--psm 6"
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise ProcessingError("OCR engine is not installed or TESSERACT_CMD is invalid") from exc


def _process_pdf(path: Path) -> ParsedDocument:
    try:
        reader = PdfReader(str(path), strict=False)
        page_count = len(reader.pages)
        if page_count == 0:
            raise ProcessingError("PDF contains no pages")
        document = pymupdf.open(str(path))
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Unreadable or corrupted PDF: {exc}") from exc

    pages: list[str] = []
    used_ocr = False
    try:
        for index in range(page_count):
            try:
                text = reader.pages[index].extract_text() or ""
            except Exception:
                text = ""
            if len(text.strip()) < 40:
                used_ocr = True
                try:
                    page = document.load_page(index)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = _ocr(image)
                except Exception as exc:
                    if not text.strip():
                        text = f"[OCR failed on page {index + 1}: {exc}]"
            pages.append(f"\n--- Page {index + 1} ---\n{text.strip()}")
    finally:
        document.close()
    return ParsedDocument(text="\n".join(pages).strip(), page_count=page_count, used_ocr=used_ocr)


def _process_image(path: Path) -> ParsedDocument:
    try:
        with Image.open(path) as source:
            frames = [frame.copy() for frame in ImageSequence.Iterator(source)]
    except Exception as exc:
        raise ProcessingError(f"Unreadable or corrupted image: {exc}") from exc
    if not frames:
        raise ProcessingError("Image contains no readable frames")
    text = [f"\n--- Page {i} ---\n{_ocr(frame).strip()}" for i, frame in enumerate(frames, 1)]
    return ParsedDocument(text="\n".join(text).strip(), page_count=len(frames), used_ocr=True)


def _frame_to_text(frame: pd.DataFrame, sheet: str) -> str:
    clean = frame.fillna("").astype(str)
    lines = [f"--- Sheet: {sheet} ---"]
    columns = [str(column) for column in clean.columns]
    for row in clean.itertuples(index=False, name=None):
        lines.extend(f"{column}: {value}" for column, value in zip(columns, row) if value)
    lines.extend(["--- Table ---", "\t".join(columns)])
    lines.extend("\t".join(row) for row in clean.itertuples(index=False, name=None))
    return "\n".join(lines)


def _process_spreadsheet(path: Path) -> ParsedDocument:
    try:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    except Exception as exc:
        raise ProcessingError(f"Unreadable or corrupted spreadsheet: {exc}") from exc
    if not sheets:
        raise ProcessingError("Spreadsheet contains no sheets")
    names = [str(name) for name in sheets]
    text = "\n\n".join(_frame_to_text(frame, str(name)) for name, frame in sheets.items())
    return ParsedDocument(text=text, page_count=len(sheets), sheets=names)


def _process_csv(path: Path) -> ParsedDocument:
    try:
        raw = path.read_bytes()
        match = from_bytes(raw).best()
        if match is None:
            raise ProcessingError("Could not determine CSV character encoding")
        decoded = str(match)
        frame = pd.read_csv(io.StringIO(decoded), dtype=str, sep=None, engine="python")
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Unreadable or corrupted CSV: {exc}") from exc
    return ParsedDocument(text=_frame_to_text(frame, "CSV"), page_count=1, sheets=["CSV"])


def process_file(path: Path) -> ParsedDocument:
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ProcessingError(f"Unsupported file type: {extension or 'unknown'}")
    if not path.exists() or path.stat().st_size == 0:
        raise ProcessingError("File is missing or empty")
    if extension == ".pdf":
        return _process_pdf(path)
    if extension in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return _process_image(path)
    if extension in {".xlsx", ".xls"}:
        return _process_spreadsheet(path)
    return _process_csv(path)
