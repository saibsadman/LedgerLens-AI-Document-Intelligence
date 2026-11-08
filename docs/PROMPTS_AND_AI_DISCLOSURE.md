# AI prompt and development disclosure

## Runtime extraction prompt

The exact prompt lives in `app/services/extraction.py` and is reproduced here for review:

> Extract invoice facts from the supplied document text. Use null for every missing or uncertain scalar value. Never infer or invent a value. Amounts must be plain decimal numbers. Currency must be an ISO 4217 code when explicit. Only include line items that are visibly present. Include short uncertainty notes and 0..1 confidence per populated field.

The Pydantic `InvoiceExtraction` model is supplied as the Structured Outputs schema. Text is capped before transmission. A model error, refusal, missing API key, or unavailable network activates the deterministic fallback and adds an extraction note. Model output is always validated again by independent arithmetic and business rules.

## AI-assisted development disclosure

This project was generated with assistance from OpenAI Codex. AI assistance was used for architecture, implementation, documentation, test scaffolding, and interface styling. The repository contains no hidden generated binaries or copied credentials. A human owner remains responsible for code review, dependency/security scanning, real-data evaluation, privacy review, deployment controls, and acceptance testing.

