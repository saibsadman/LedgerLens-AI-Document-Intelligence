from decimal import Decimal

from app.services.extraction import extract_deterministic


def test_extracts_invoice_without_inventing_values():
    text = """INVOICE
Invoice No: INV-2025-042
Invoice Date: 05 January 2025
Supplier: Acme Trading Ltd
Bill To: Northwind Stores
Currency: USD
Consulting service  2  100.00  200.00
Subtotal: 200.00
VAT: 30.00
Grand Total: 230.00
"""
    result = extract_deterministic(text)
    assert result.invoice_number == "INV-2025-042"
    assert result.supplier_name == "Acme Trading Ltd"
    assert result.customer_name == "Northwind Stores"
    assert result.subtotal == Decimal("200.00")
    assert result.total == Decimal("230.00")
    assert result.currency == "USD"
    assert result.line_items[0].amount == Decimal("200.00")


def test_missing_values_remain_null():
    result = extract_deterministic("Invoice No: ABC-99\nSupplier: Example Corp")
    assert result.invoice_date is None
    assert result.total is None
    assert result.currency is None
