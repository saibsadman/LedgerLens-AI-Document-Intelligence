from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from app.schemas import InvoiceExtraction


@dataclass
class Issue:
    code: str
    field: str | None
    severity: str
    message: str
    expected: str | None = None
    actual: str | None = None


REQUIRED_FIELDS = ("invoice_number", "invoice_date", "supplier_name", "total", "currency")


def validate_invoice(
    invoice: InvoiceExtraction,
    duplicate_check: Callable[[str, str], bool] | None = None,
    tolerance: Decimal = Decimal("0.02"),
) -> list[Issue]:
    issues: list[Issue] = []
    for field in REQUIRED_FIELDS:
        if getattr(invoice, field) in (None, ""):
            issues.append(
                Issue("MISSING_REQUIRED", field, "error", f"Required field '{field}' is missing")
            )

    for field in ("subtotal", "tax", "total"):
        value = getattr(invoice, field)
        if value is not None and value < 0:
            issues.append(
                Issue(
                    "NEGATIVE_AMOUNT",
                    field,
                    "error",
                    f"{field} cannot be negative",
                    actual=str(value),
                )
            )

    if invoice.subtotal is not None and invoice.tax is not None and invoice.total is not None:
        expected = invoice.subtotal + invoice.tax
        if abs(expected - invoice.total) > tolerance:
            issues.append(
                Issue(
                    "TOTAL_MISMATCH",
                    "total",
                    "error",
                    "Subtotal plus tax does not equal total",
                    str(expected),
                    str(invoice.total),
                )
            )

    line_sum = sum(
        (item.amount for item in invoice.line_items if item.amount is not None), Decimal("0")
    )
    if (
        invoice.line_items
        and invoice.subtotal is not None
        and abs(line_sum - invoice.subtotal) > tolerance
    ):
        issues.append(
            Issue(
                "LINE_ITEMS_MISMATCH",
                "subtotal",
                "warning",
                "Line item amounts do not equal subtotal",
                str(line_sum),
                str(invoice.subtotal),
            )
        )

    for index, item in enumerate(invoice.line_items):
        if item.quantity is not None and item.unit_price is not None and item.amount is not None:
            expected = item.quantity * item.unit_price
            if abs(expected - item.amount) > tolerance:
                issues.append(
                    Issue(
                        "LINE_ITEM_CALCULATION",
                        f"line_items.{index}.amount",
                        "warning",
                        f"Line item {index + 1} quantity × unit price mismatch",
                        str(expected),
                        str(item.amount),
                    )
                )

    if invoice.invoice_number and invoice.supplier_name and duplicate_check:
        if duplicate_check(invoice.invoice_number, invoice.supplier_name):
            issues.append(
                Issue(
                    "DUPLICATE_INVOICE",
                    "invoice_number",
                    "error",
                    "Invoice number already exists for this supplier",
                )
            )

    for field, confidence in invoice.field_confidence.items():
        if confidence < 0.6:
            issues.append(
                Issue(
                    "LOW_CONFIDENCE",
                    field,
                    "warning",
                    f"Low extraction confidence ({confidence:.0%})",
                    actual=str(confidence),
                )
            )
    return issues
