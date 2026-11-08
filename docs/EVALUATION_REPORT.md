# Evaluation report

## Method

`evaluation/run_evaluation.py` creates three fixed labeled synthetic invoices (digital PDF, XLSX, CSV), runs the real document parser and deterministic extractor, and compares eight target fields per document using normalized exact match. It records document success/failure and end-to-end parser + extractor latency using a monotonic clock.

The authoritative measured output is `evaluation/results.json`, generated on the test machine. Test and benchmark commands are listed in the root README.

## Results

Measured on 2026-11-08 with Python 3.12.10 on the submission machine:

| Metric | Measured result |
|---|---:|
| Labeled documents | 3 |
| Evaluated scalar fields | 24 |
| Exact field accuracy | 100.00% |
| Document success rate | 100.00% |
| Failure rate | 0.00% |
| Mean parser + extraction time | 0.0155 seconds/document |
| Nearest-rank p95 time | 0.0233 seconds/document |
| PDF field accuracy | 100.00% |
| XLSX field accuracy | 100.00% |
| CSV field accuracy | 100.00% |

The machine-readable authoritative output is committed at `evaluation/results.json`. Timing will vary by machine and does not include external LLM latency or OCR because these benchmark cases use digital text/tabular input.

## Interpretation and limitations

The bundled three-document synthetic set is an integration smoke benchmark. It does not estimate production accuracy. OCR accuracy is separately covered by mocked pipeline tests because Tesseract availability and language packs vary by host.

Production evaluation should use at least several hundred access-controlled, double-labeled documents stratified by supplier, format, language, scan quality, page count, and template. Measure field precision/recall/F1, normalized amount accuracy, line-item row F1, calibration by confidence bucket, p50/p95/p99 latency, throughput, cost, and failure taxonomy. Lock the dataset before tuning and retain a blind holdout set.

