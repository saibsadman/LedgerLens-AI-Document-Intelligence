# Recorded walkthrough script

Use this 4–6 minute script when recording the required walkthrough after local verification.

1. Show the repository structure and architecture diagram.
2. Start `docker compose up --build`; open the health endpoint and Swagger at `/docs`.
3. Open the web UI, upload a digital PDF, a scanned image/TIFF, an XLSX workbook, and a CSV together.
4. Show queued/processing progress and explain the worker queue and page-by-page OCR.
5. Open a completed document. Review extracted fields, line items, confidence, raw source text, and validation issues.
6. Introduce an incorrect total through a test document; show the subtotal + tax mismatch.
7. Correct the field and save; show that it is audited and revalidated.
8. Select a PDF and Excel document, click **Compare fields**, and show matching/different fields.
9. Search by supplier/invoice text and demonstrate the semantic endpoint in Swagger.
10. Upload a corrupt PDF, show isolated failure, and use **Reprocess**.
11. Run `pytest --cov=app` and `python evaluation/run_evaluation.py`; show measured `evaluation/results.json`.
12. Close with security/scaling notes and state that GitHub upload/deployment is intentionally deferred.

Do not include real financial documents, environment files, API keys, customer identifiers, or terminal history containing secrets in the recording.

