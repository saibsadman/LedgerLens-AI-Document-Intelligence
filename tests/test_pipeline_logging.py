import logging
from decimal import Decimal

from app.schemas import InvoiceExtraction
from app.services.pipeline import _log_pre_validation_payload


def test_raw_text_and_structured_json_are_logged_before_validation(caplog):
    raw_text = "Bengal Office Supplies Ltd.\nTOTAL (BDT)\n20,685.00"
    invoice = InvoiceExtraction(
        supplier_name="Bengal Office Supplies Ltd.",
        total=Decimal("20685.00"),
        currency="BDT",
    )

    with caplog.at_level(logging.DEBUG, logger="uvicorn.error.extraction_trace"):
        _log_pre_validation_payload("document-123", raw_text, invoice)

    messages = "\n".join(caplog.messages)
    assert "Raw extracted text before validation" in messages
    assert raw_text in messages
    assert "Structured JSON before validation" in messages
    assert '"supplier_name": "Bengal Office Supplies Ltd."' in messages
    assert '"total": "20685.00"' in messages
