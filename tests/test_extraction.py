from decimal import Decimal

from app.schemas import InvoiceExtraction
from app.services.extraction import _merge_missing_text_evidence, extract_deterministic


def test_simple_labeled_invoice_layout_extracts_expected_fields():
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

    ambiguous_header = extract_deterministic(
        "Office Supplies and Stationery\nINVOICE\nInvoice No: ABC-100"
    )
    assert ambiguous_header.supplier_name is None
    assert ambiguous_header.total is None


def test_header_supplier_and_split_line_total_layout():
    text = """--- Page 1 ---
Bengal Office Supplies Ltd.
42 Motijheel Commercial Area, Dhaka
INVOICE
Invoice No: BOS-2026-104
Invoice Date: 2026-11-08
TOTAL (BDT)
20,685.00
"""
    result = extract_deterministic(text)
    assert result.supplier_name == "Bengal Office Supplies Ltd."
    assert result.total == Decimal("20685.00")
    assert result.currency == "BDT"
    assert result.customer_name is None
    assert result.field_confidence["supplier_name"] == 0.62


def test_ai_null_fields_recover_only_explicit_text_evidence():
    evidence = extract_deterministic("Bengal Office Supplies Ltd.\nINVOICE\nTOTAL (BDT)\n20,685.00")
    ai_result = InvoiceExtraction(invoice_number="LLM-KEPT-001")

    merged = _merge_missing_text_evidence(ai_result, evidence)

    assert merged.invoice_number == "LLM-KEPT-001"
    assert merged.supplier_name == "Bengal Office Supplies Ltd."
    assert merged.total == Decimal("20685.00")
    assert merged.currency == "BDT"
    assert merged.customer_name is None


def test_invoice_summary_table_is_not_misclassified_as_line_item():
    text = """Invoice No: REVIEW-2026-077
Invoice Date: 2026-11-08
Supplier: Harbor Consulting
Subtotal: 1000.00
Tax: 150.00
Grand Total: 1200.00
REVIEW-2026-077\t2026-11-08\tHarbor Consulting\tUSD\t1000.00\t150.00\t1200.00
"""
    result = extract_deterministic(text)
    assert result.line_items == []
