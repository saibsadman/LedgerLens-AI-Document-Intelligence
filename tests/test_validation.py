from datetime import date
from decimal import Decimal

from app.schemas import InvoiceExtraction, LineItem
from app.services.validation import validate_invoice


def valid_invoice(**changes):
    data = dict(
        invoice_number="A-1",
        invoice_date=date(2025, 1, 1),
        supplier_name="Acme",
        subtotal=Decimal("100"),
        tax=Decimal("15"),
        total=Decimal("115"),
        currency="USD",
        line_items=[
            LineItem(
                description="Work",
                quantity=Decimal("2"),
                unit_price=Decimal("50"),
                amount=Decimal("100"),
            )
        ],
    )
    data.update(changes)
    return InvoiceExtraction(**data)


def test_valid_invoice_has_no_issues():
    assert validate_invoice(valid_invoice()) == []


def test_detects_totals_lines_duplicates_and_missing_fields():
    invoice = valid_invoice(total=Decimal("120"), subtotal=Decimal("90"), currency=None)
    issues = validate_invoice(invoice, lambda *_: True)
    codes = {issue.code for issue in issues}
    assert {
        "MISSING_REQUIRED",
        "TOTAL_MISMATCH",
        "LINE_ITEMS_MISMATCH",
        "DUPLICATE_INVOICE",
    } <= codes


def test_amount_tolerance_avoids_rounding_false_positive():
    invoice = valid_invoice(subtotal=Decimal("100.001"), tax=Decimal("14.999"))
    assert not any(issue.code == "TOTAL_MISMATCH" for issue in validate_invoice(invoice))
