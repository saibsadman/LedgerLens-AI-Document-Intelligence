# Evaluation

Run `python evaluation/run_evaluation.py` from the repository root. It generates a fixed labeled synthetic set containing one digital PDF, one XLSX workbook, and one CSV-like invoice, processes them through the real parsers and deterministic extractor, and writes measured results to `results.json`.

This small smoke benchmark proves repeatability; it is not a claim of production accuracy. Before rollout, replace or extend `CASES` with a representative, access-controlled sample of real invoices, including scans, rotated pages, handwriting, multiple languages, dense line-item tables, and known corrupt files. Report field-level precision/recall by supplier template and confidence threshold.

