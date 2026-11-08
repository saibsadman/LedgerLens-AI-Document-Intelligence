from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from dateutil import parser as date_parser

from app.config import settings
from app.schemas import InvoiceExtraction, LineItem

LABEL_PATTERNS = {
    "invoice_number": [
        r"(?m)^[ \t]*(?:invoice|inv)[ \t]*(?:no\.?|number|id|#)[ \t:#_-]*([A-Z0-9][A-Z0-9./_-]{2,})"
    ],
    "invoice_date": [r"(?:invoice\s*)?date\s*[:#-]?\s*([^\n|]{4,30})"],
    "supplier_name": [r"(?:supplier|vendor|seller|from)\s*[:#-]\s*([^\n|]{2,100})"],
    "customer_name": [r"(?:customer|client|bill\s*to|buyer)\s*[:#-]\s*([^\n|]{2,100})"],
    "subtotal": [
        r"(?:sub[ -]?total|net\s+amount)\s*[:#]?\s*(?:[A-Z]{3}|[$€£৳])?\s*([\d,]+(?:\.\d{1,4})?)"
    ],
    "tax": [
        r"(?:tax|vat|gst)(?:\s*\([^)]*\)|\s*\d+(?:\.\d+)?%)?\s*[:#]?\s*(?:[A-Z]{3}|[$€£৳])?\s*([\d,]+(?:\.\d{1,4})?)"
    ],
    "total": [
        r"(?m)^[ \t]*(?:grand[ \t]+total|amount[ \t]+due|invoice[ \t]+total|(?<!sub)total)"
        r"[ \t]*(?:\([A-Z]{3}\)|[A-Z]{3}|[$€£৳])?[ \t]*[:#-]?[ \t]*"
        r"(?:\r?\n[ \t]*)?([\d,]+(?:\.\d{1,4})?)[ \t]*$"
    ],
}

CURRENCY_MAP = {"$": "USD", "€": "EUR", "£": "GBP", "৳": "BDT", "₹": "INR"}

COMPANY_SUFFIX = re.compile(
    r"\b(?:ltd\.?|limited|llc|l\.l\.c\.?|inc\.?|incorporated|corp\.?|corporation|plc|company|co\.?)$",
    flags=re.IGNORECASE,
)

SCALAR_EVIDENCE_FIELDS = (
    "invoice_number",
    "invoice_date",
    "supplier_name",
    "customer_name",
    "subtotal",
    "tax",
    "total",
    "currency",
)


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" \t:#|-")
    return None


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(re.sub(r"[^\d.-]", "", value.replace(",", "")))
    except InvalidOperation:
        return None


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date_parser.parse(value, fuzzy=True, dayfirst=False).date()
    except (ValueError, OverflowError):
        return None


def _currency(text: str) -> str | None:
    codes = re.findall(r"\b(USD|EUR|GBP|BDT|INR|CAD|AUD|JPY|CNY|SGD|AED)\b", text, re.I)
    if codes:
        return codes[-1].upper()
    for symbol, code in CURRENCY_MAP.items():
        if symbol in text:
            return code
    return None


def _supplier_from_header(text: str) -> str | None:
    """Find an evidence-backed supplier in the first invoice header lines.

    Unlabeled text is accepted only when it ends in a recognized legal company
    suffix. Ambiguous header text remains null instead of being guessed.
    """
    header_lines: list[str] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split()).strip(" |")
        if not line or re.fullmatch(r"---\s*Page\s+\d+\s*---", line, re.IGNORECASE):
            continue
        if re.match(r"^(?:invoice|tax invoice)\b", line, re.IGNORECASE):
            break
        header_lines.append(line)
        if len(header_lines) >= 12:
            break

    excluded_labels = re.compile(
        r"^(?:bill\s*to|ship\s*to|customer|client|buyer|invoice|date|address)\b",
        re.IGNORECASE,
    )
    for line in header_lines:
        if excluded_labels.search(line) or ":" in line:
            continue
        if len(line) <= 120 and len(line.split()) >= 2 and COMPANY_SUFFIX.search(line):
            return line
    return None


def _line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    row_pattern = re.compile(
        r"^\s*(?P<description>[A-Za-z][\w /().,#&+-]{2,}?)\s{2,}|^\s*(?P<tabdesc>[^\t]+)\t"
    )
    for line in text.splitlines():
        tabular_cells = [cell.strip() for cell in line.split("\t")]
        if len(tabular_cells) >= 5 and any(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell) for cell in tabular_cells
        ):
            # This is an invoice summary row, not a product/service line item.
            continue
        match = row_pattern.search(line)
        if not match:
            continue
        numbers = re.findall(r"-?\d[\d,]*(?:\.\d+)?", line)
        if len(numbers) < 2:
            continue
        description = (match.group("description") or match.group("tabdesc") or "").strip()
        if re.search(r"subtotal|grand total|amount due|invoice|date|tax", description, re.I):
            continue
        values = [_decimal(number) for number in numbers]
        values = [value for value in values if value is not None]
        if len(values) >= 3:
            items.append(
                LineItem(
                    description=description[:300],
                    quantity=values[-3],
                    unit_price=values[-2],
                    amount=values[-1],
                    confidence=0.62,
                )
            )
        else:
            items.append(
                LineItem(
                    description=description[:300],
                    quantity=values[-2],
                    amount=values[-1],
                    confidence=0.5,
                )
            )
        if len(items) >= 200:
            break
    return items


def extract_deterministic(text: str) -> InvoiceExtraction:
    values = {key: _first_match(text, patterns) for key, patterns in LABEL_PATTERNS.items()}
    supplier_from_header = False
    if values["supplier_name"] is None:
        values["supplier_name"] = _supplier_from_header(text)
        supplier_from_header = values["supplier_name"] is not None
    parsed = InvoiceExtraction(
        invoice_number=values["invoice_number"],
        invoice_date=_date(values["invoice_date"]),
        supplier_name=values["supplier_name"],
        customer_name=values["customer_name"],
        subtotal=_decimal(values["subtotal"]),
        tax=_decimal(values["tax"]),
        total=_decimal(values["total"]),
        currency=_currency(text),
        line_items=_line_items(text),
    )
    populated = [name for name in LABEL_PATTERNS if getattr(parsed, name, None) is not None]
    parsed.field_confidence = {name: 0.72 for name in populated}
    if supplier_from_header:
        parsed.field_confidence["supplier_name"] = 0.62
    parsed.extraction_notes = ["Deterministic parser used; verify fields with low confidence."]
    return parsed


def _merge_missing_text_evidence(
    primary: InvoiceExtraction, evidence: InvoiceExtraction
) -> InvoiceExtraction:
    """Fill only null AI fields with values explicitly found in source text."""
    merged = primary.model_copy(deep=True)
    recovered: list[str] = []
    for field in SCALAR_EVIDENCE_FIELDS:
        if getattr(merged, field) is None and getattr(evidence, field) is not None:
            setattr(merged, field, getattr(evidence, field))
            recovered.append(field)
            if field in evidence.field_confidence:
                merged.field_confidence[field] = evidence.field_confidence[field]
    if recovered:
        merged.extraction_notes.append(
            "Recovered explicit text evidence for: " + ", ".join(recovered) + "."
        )
    return merged


def extract_invoice(text: str) -> InvoiceExtraction:
    if not settings.openai_api_key:
        return extract_deterministic(text)
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = """Extract invoice facts from the supplied document text.
Use null for every missing or uncertain scalar value. Never infer or invent a value.
Amounts must be plain decimal numbers. Currency must be an ISO 4217 code when explicit.
The supplier can be an unlabeled legal company name in the top invoice header.
A total label and its amount can appear on adjacent extracted lines.
Only include line items that are visibly present. Include short uncertainty notes and 0..1 confidence per populated field."""
    try:
        response = client.responses.parse(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:120_000]},
            ],
            text_format=InvoiceExtraction,
        )
        if response.output_parsed is None:
            fallback = extract_deterministic(text)
            fallback.extraction_notes.append("LLM returned no parsed output; fallback parser used.")
            return fallback
        return _merge_missing_text_evidence(response.output_parsed, extract_deterministic(text))
    except Exception as exc:
        fallback = extract_deterministic(text)
        fallback.extraction_notes.append(
            f"LLM unavailable ({type(exc).__name__}); fallback parser used."
        )
        return fallback
