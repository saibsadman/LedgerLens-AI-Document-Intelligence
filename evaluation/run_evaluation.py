from __future__ import annotations

import json
import math
import statistics
import tempfile
import time
from pathlib import Path

import pandas as pd
import pymupdf

from app.services.document_processor import process_file
from app.services.extraction import extract_deterministic

CASES = [
    {
        "invoice_number": "BENCH-001",
        "invoice_date": "2025-01-05",
        "supplier_name": "Acme Trading Ltd",
        "customer_name": "Northwind Stores",
        "subtotal": "200.00",
        "tax": "30.00",
        "total": "230.00",
        "currency": "USD",
    },
    {
        "invoice_number": "BENCH-002",
        "invoice_date": "2025-02-10",
        "supplier_name": "Dhaka Office Supply",
        "customer_name": "Contoso Ltd",
        "subtotal": "500.00",
        "tax": "75.00",
        "total": "575.00",
        "currency": "BDT",
    },
    {
        "invoice_number": "BENCH-003",
        "invoice_date": "2025-03-20",
        "supplier_name": "Harbor Consulting",
        "customer_name": "Alpine Retail",
        "subtotal": "1200.00",
        "tax": "180.00",
        "total": "1380.00",
        "currency": "EUR",
    },
]


def invoice_text(case: dict[str, str]) -> str:
    return f"""INVOICE
Invoice No: {case["invoice_number"]}
Invoice Date: {case["invoice_date"]}
Supplier: {case["supplier_name"]}
Bill To: {case["customer_name"]}
Currency: {case["currency"]}
Professional service  2  {float(case["subtotal"]) / 2:.2f}  {case["subtotal"]}
Subtotal: {case["subtotal"]}
Tax: {case["tax"]}
Grand Total: {case["total"]}
"""


def build_dataset(root: Path) -> list[tuple[Path, dict[str, str]]]:
    rows = []
    pdf = root / "invoice.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), invoice_text(CASES[0]), fontsize=11)
    document.save(pdf)
    document.close()
    rows.append((pdf, CASES[0]))

    xlsx = root / "invoice.xlsx"
    pd.DataFrame(
        [
            {
                "Invoice No": CASES[1]["invoice_number"],
                "Invoice Date": CASES[1]["invoice_date"],
                "Supplier": CASES[1]["supplier_name"],
                "Bill To": CASES[1]["customer_name"],
                "Currency": CASES[1]["currency"],
                "Subtotal": CASES[1]["subtotal"],
                "Tax": CASES[1]["tax"],
                "Grand Total": CASES[1]["total"],
            }
        ]
    ).to_excel(xlsx, index=False)
    rows.append((xlsx, CASES[1]))

    csv = root / "invoice.csv"
    pd.DataFrame(
        [
            {
                "Invoice No": CASES[2]["invoice_number"],
                "Invoice Date": CASES[2]["invoice_date"],
                "Supplier": CASES[2]["supplier_name"],
                "Bill To": CASES[2]["customer_name"],
                "Currency": CASES[2]["currency"],
                "Subtotal": CASES[2]["subtotal"],
                "Tax": CASES[2]["tax"],
                "Grand Total": CASES[2]["total"],
            }
        ]
    ).to_csv(csv, index=False)
    rows.append((csv, CASES[2]))
    return rows


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip().lower()


def main() -> None:
    total_fields = correct_fields = successful = 0
    latencies: list[float] = []
    details = []
    with tempfile.TemporaryDirectory() as temp:
        for path, expected in build_dataset(Path(temp)):
            started = time.perf_counter()
            try:
                parsed = process_file(path)
                extraction = extract_deterministic(parsed.text)
                actual = extraction.model_dump(mode="json")
                matched = 0
                for field, value in expected.items():
                    total_fields += 1
                    if normalize(actual.get(field)) == normalize(value):
                        correct_fields += 1
                        matched += 1
                successful += 1
                details.append(
                    {"file": path.name, "success": True, "field_accuracy": matched / len(expected)}
                )
            except Exception as exc:
                details.append({"file": path.name, "success": False, "error": str(exc)})
            latencies.append(time.perf_counter() - started)
    result = {
        "dataset": "3 generated labeled synthetic invoices (digital PDF, XLSX, CSV)",
        "documents": len(CASES),
        "field_accuracy": correct_fields / total_fields if total_fields else 0,
        "document_success_rate": successful / len(CASES),
        "failure_rate": (len(CASES) - successful) / len(CASES),
        "mean_processing_seconds": statistics.mean(latencies),
        "p95_processing_seconds": sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)],
        "details": details,
    }
    output = Path(__file__).with_name("results.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
