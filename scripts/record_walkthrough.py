from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pandas as pd
import pymupdf
from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "ledgerlens_walkthrough.webm"
BASE_URL = "http://127.0.0.1:8000"


def invoice_text(number: str, supplier: str, customer: str, total: str) -> str:
    return f"""INVOICE
Invoice No: {number}
Invoice Date: 2026-11-08
Supplier: {supplier}
Bill To: {customer}
Currency: USD
Implementation service  2  500.00  1000.00
Subtotal: 1000.00
Tax: 150.00
Grand Total: {total}
"""


def create_samples(directory: Path) -> list[Path]:
    pdf_path = directory / "acme_invoice.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        invoice_text("ACME-2026-100", "Acme Trading Ltd", "Northwind Stores", "1150.00"),
        fontsize=11,
    )
    document.save(pdf_path)
    document.close()

    common = {
        "Invoice No": "ACME-2026-100",
        "Invoice Date": "2026-11-08",
        "Supplier": "Acme Trading Ltd",
        "Bill To": "Northwind Stores",
        "Currency": "USD",
        "Subtotal": "1000.00",
        "Tax": "150.00",
        "Grand Total": "1150.00",
    }
    xlsx_path = directory / "acme_invoice.xlsx"
    with pd.ExcelWriter(xlsx_path) as writer:
        pd.DataFrame([common]).to_excel(writer, sheet_name="Invoice", index=False)
        pd.DataFrame(
            [
                {
                    "Description": "Implementation service",
                    "Quantity": 2,
                    "Unit price": 500,
                    "Amount": 1000,
                }
            ]
        ).to_excel(writer, sheet_name="Line Items", index=False)

    review_path = directory / "review_invoice.csv"
    pd.DataFrame(
        [
            {
                "Invoice No": "REVIEW-2026-077",
                "Invoice Date": "2026-11-08",
                "Supplier": "Harbor Consulting",
                "Bill To": "Alpine Retail",
                "Currency": "USD",
                "Subtotal": "1000.00",
                "Tax": "150.00",
                "Grand Total": "1200.00",
            }
        ]
    ).to_csv(review_path, index=False)
    return [pdf_path, xlsx_path, review_path]


def wait_for_server(timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/api/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Preview server did not become ready")


def caption(page: Page, title: str, body: str, seconds: float = 3.2) -> None:
    page.evaluate(
        """([title, body]) => {
          let node = document.getElementById('walkthrough-caption');
          if (!node) {
            node = document.createElement('div');
            node.id = 'walkthrough-caption';
            node.innerHTML = '<strong></strong><span></span>';
            Object.assign(node.style, {
              position: 'fixed', left: '50%', bottom: '24px', transform: 'translateX(-50%)',
              width: 'min(720px, calc(100vw - 48px))', padding: '15px 20px', borderRadius: '12px',
              color: 'white', background: 'rgba(10, 35, 32, .94)', zIndex: '999999',
              boxShadow: '0 12px 40px rgba(0,0,0,.28)', display: 'flex', flexDirection: 'column',
              gap: '4px', fontFamily: 'Arial, sans-serif', pointerEvents: 'none'
            });
            Object.assign(node.querySelector('strong').style, {fontSize: '17px', letterSpacing: '.01em'});
            Object.assign(node.querySelector('span').style, {fontSize: '13px', color: '#c8ded9'});
            document.body.appendChild(node);
          }
          node.querySelector('strong').textContent = title;
          node.querySelector('span').textContent = body;
          node.animate([{opacity: .2, transform: 'translateY(10px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 300});
        }""",
        [title, body],
    )
    page.wait_for_timeout(seconds * 1000)


def focus(locator: Locator) -> None:
    locator.scroll_into_view_if_needed()
    locator.evaluate(
        """node => {
          document.querySelectorAll('.walkthrough-focus').forEach(el => el.classList.remove('walkthrough-focus'));
          node.classList.add('walkthrough-focus');
          node.style.outline = '3px solid #35b99d';
          node.style.outlineOffset = '4px';
          node.style.transition = 'outline .2s';
        }"""
    )


def record(sample_files: list[Path], video_directory: Path) -> Path:
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    executable = chrome if chrome.exists() else edge
    if not executable.exists():
        raise RuntimeError("Chrome or Microsoft Edge is required to record the walkthrough")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(executable), headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir=str(video_directory),
            record_video_size={"width": 1440, "height": 900},
            color_scheme="light",
        )
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle")
        caption(
            page,
            "LedgerLens — AI Document Intelligence",
            "A real end-to-end walkthrough: ingestion, extraction, validation, correction, search and cross-verification.",
            4,
        )

        dropzone = page.locator(".dropzone")
        focus(dropzone)
        caption(
            page,
            "1 · Multi-format document ingestion",
            "Uploading a digital PDF, a multi-sheet Excel workbook and a CSV invoice in one batch.",
            2.5,
        )
        page.locator('input[type="file"]').set_input_files([str(path) for path in sample_files])
        page.get_by_text(re.compile(r"3 documents added", re.IGNORECASE)).wait_for(timeout=30_000)
        page.locator(".table-card").scroll_into_view_if_needed()
        caption(
            page,
            "2 · Background processing and status tracking",
            "Each file is parsed independently, extracted into structured JSON, validated and indexed for search.",
            4,
        )

        review_row = page.locator("tbody tr").filter(has_text="review_invoice.csv")
        focus(review_row)
        caption(
            page,
            "3 · Automatic exception routing",
            "The CSV has an intentional total mismatch, so LedgerLens routes it to the review queue.",
            3,
        )
        review_row.locator(".doc-name").click()
        page.get_by_text("Validation report").wait_for()
        issue_card = page.locator(".issue-card")
        focus(issue_card)
        caption(
            page,
            "4 · Evidence-backed validation",
            "Subtotal plus tax is 1,150, but the source total is 1,200. The exact expected and actual values are shown.",
            4,
        )

        total_label = page.locator(".field-grid label").filter(
            has=page.locator("span", has_text=re.compile(r"^total\b"))
        )
        total_input = total_label.locator("input")
        focus(total_label)
        total_input.fill("1150.00")
        caption(
            page,
            "5 · Audited manual correction",
            "A reviewer corrects the value. The API validates the new schema before persistence and records the change.",
            3,
        )
        page.get_by_role("button", name="Save corrections").click()
        page.get_by_text("All checks passed").wait_for(timeout=15_000)
        focus(page.locator(".all-clear"))
        caption(
            page,
            "6 · Instant revalidation",
            "The corrected document now passes all arithmetic and required-field checks.",
            3.5,
        )
        page.locator(".panel-head .icon-button").click()

        for filename in ("acme_invoice.pdf", "acme_invoice.xlsx"):
            row = page.locator("tbody tr").filter(has_text=filename)
            row.locator(".compare-check").click()
        page.get_by_role("button", name="Compare fields").click()
        page.get_by_text("Documents match").wait_for()
        focus(page.locator(".comparison-list"))
        caption(
            page,
            "7 · PDF-to-Excel cross-verification",
            "Invoice number, date, supplier, customer, amounts and currency match across both source documents.",
            4.5,
        )
        page.locator(".compare-panel .icon-button").click()

        search = page.locator(".search-box input")
        focus(search)
        search.fill("Harbor Consulting")
        page.wait_for_timeout(700)
        caption(
            page,
            "8 · Searchable document register",
            "Reviewers can search names, invoice fields and full extracted text; a semantic-search API is also available.",
            4,
        )
        search.fill("")
        page.wait_for_timeout(700)
        page.locator(".hero-row").scroll_into_view_if_needed()
        caption(
            page,
            "Ready for production hardening",
            "FastAPI, PostgreSQL, Redis/Celery, OCR, audit history, Docker, automated tests and a measured evaluation harness are included.",
            5,
        )
        video = page.video
        context.close()
        browser.close()
        if video is None:
            raise RuntimeError("Playwright did not create a video")
        return Path(video.path())


def main() -> None:
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("Build the frontend first: cd frontend && npm run build")

    with tempfile.TemporaryDirectory(prefix="ledgerlens-walkthrough-") as temp_name:
        temp = Path(temp_name)
        sample_directory = temp / "samples"
        sample_directory.mkdir()
        samples = create_samples(sample_directory)
        environment = os.environ.copy()
        database_path = (temp / "walkthrough.sqlite3").as_posix()
        environment.update(
            {
                "DATABASE_URL": f"sqlite:///{database_path}",
                "STORAGE_PATH": str(temp / "uploads"),
                "USE_CELERY": "false",
                "OPENAI_API_KEY": "",
                "ALLOWED_ORIGINS": BASE_URL,
            }
        )
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_for_server()
            recorded = record(samples, temp / "video")
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recorded, OUTPUT)
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
        print(f"Walkthrough recorded: {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
