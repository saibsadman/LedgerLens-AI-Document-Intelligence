from decimal import Decimal
from pathlib import Path

import pandas as pd
import pymupdf
from PIL import Image

from app.services import document_processor as processor
from app.services.extraction import extract_deterministic


def test_csv_parsing_handles_structured_rows(tmp_path: Path):
    path = tmp_path / "invoice.csv"
    path.write_text("Description,Quantity,Amount\nService,2,200\n", encoding="utf-8")
    result = processor.process_file(path)
    assert result.page_count == 1
    assert "Description\tQuantity\tAmount" in result.text
    assert "Service\t2\t200" in result.text


def test_multisheet_xlsx(tmp_path: Path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"Invoice": ["A-1"]}).to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame({"Item": ["Service"]}).to_excel(writer, sheet_name="Lines", index=False)
    result = processor.process_file(path)
    assert result.page_count == 2
    assert result.sheets == ["Summary", "Lines"]


def test_multiframe_image_uses_ocr(tmp_path: Path, monkeypatch):
    path = tmp_path / "scan.tiff"
    frames = [Image.new("RGB", (100, 100), "white"), Image.new("RGB", (100, 100), "white")]
    frames[0].save(path, save_all=True, append_images=frames[1:])
    calls = []
    monkeypatch.setattr(processor, "_ocr", lambda image: calls.append(image.size) or "invoice text")
    result = processor.process_file(path)
    assert result.page_count == 2
    assert len(calls) == 2
    assert result.used_ocr is True


def test_corrupt_pdf_has_safe_error(tmp_path: Path):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not-a-pdf")
    try:
        processor.process_file(path)
    except processor.ProcessingError as exc:
        assert "corrupted PDF" in str(exc)
    else:
        raise AssertionError("corrupted PDF should fail")


def test_digital_pdf_header_supplier_and_split_total_regression(tmp_path: Path):
    path = tmp_path / "bengal-office-supplies.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        """Bengal Office Supplies Ltd.
42 Motijheel Commercial Area, Dhaka
INVOICE
Invoice No: BOS-2026-104
Invoice Date: 2026-11-08
TOTAL (BDT)
20,685.00""",
        fontsize=11,
    )
    document.save(path)
    document.close()

    parsed = processor.process_file(path)
    extracted = extract_deterministic(parsed.text)

    assert parsed.used_ocr is False
    assert "Bengal Office Supplies Ltd." in parsed.text
    assert "TOTAL (BDT)\n20,685.00" in parsed.text
    assert extracted.supplier_name == "Bengal Office Supplies Ltd."
    assert extracted.total == Decimal("20685.00")
    assert extracted.currency == "BDT"
