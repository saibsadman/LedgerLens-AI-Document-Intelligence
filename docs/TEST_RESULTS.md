# Test and build results

Verified on 2026-11-08.

| Check | Result |
|---|---|
| Backend automated tests | 19 passed, 0 failed |
| Backend statement coverage | 82% |
| Python lint/import checks | Passed |
| Evaluation runner | Passed; output written to `evaluation/results.json` |
| Frontend TypeScript check | Passed |
| Frontend Vite production build | Passed; 1,567 modules transformed |
| Frontend dependency audit | 0 known vulnerabilities at install time |
| Recorded walkthrough | 42.56 seconds, 1440×900 VP9 WebM, visually inspected |

Commands used:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check app tests evaluation
.\.venv\Scripts\python.exe evaluation\run_evaluation.py
cd frontend
npm run build
```

OCR execution is unit-tested with a mocked engine so CI does not depend on an operating-system Tesseract installation. The Docker image installs Tesseract and is the recommended end-to-end OCR environment.

