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
        r"(?:grand\s+total|amount\s+due|invoice\s+total|(?<!sub)total)\s*[:#]?\s*(?:[A-Z]{3}|[$€£৳])?\s*([\d,]+(?:\.\d{1,4})?)"
    ],
}

CURRENCY_MAP = {"$": "USD", "€": "EUR", "£": "GBP", "৳": "BDT", "₹": "INR"}


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


def _line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    row_pattern = re.compile(
        r"^\s*(?P<description>[A-Za-z][\w /().,#&+-]{2,}?)\s{2,}|^\s*(?P<tabdesc>[^\t]+)\t"
    )
    for line in text.splitlines():
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
    parsed.extraction_notes = ["Deterministic parser used; verify fields with low confidence."]
    return parsed


def extract_invoice(text: str) -> InvoiceExtraction:
    if not settings.openai_api_key:
        return extract_deterministic(text)
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = """Extract invoice facts from the supplied document text.
Use null for every missing or uncertain scalar value. Never infer or invent a value.
Amounts must be plain decimal numbers. Currency must be an ISO 4217 code when explicit.
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
        return response.output_parsed
    except Exception as exc:
        fallback = extract_deterministic(text)
        fallback.extraction_notes.append(
            f"LLM unavailable ({type(exc).__name__}); fallback parser used."
        )
        return fallback
