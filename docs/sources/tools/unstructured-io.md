---
source_url: "https://github.com/Unstructured-IO/unstructured"
source_title: "Unstructured — open-source Python library for document ingestion (Apache 2.0)"
source_author: "Unstructured Technologies, Inc."
source_date: ""
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["unstructured", "document-ingestion", "rag-preprocessor", "orchestrated", "open-source", "apache-2", "western-pretraining"]
archived_pdf: ""
status: stub
---

Unstructured — open-source Apache-2.0 Python library for parsing diverse document formats (PDF, DOCX, HTML, images) into structured chunks for downstream RAG / extraction pipelines. Western-origin (Unstructured Technologies, Inc., USA). The OSS library is `pip install unstructured` (with optional `[all-docs]` extras for PDF/Office handlers).

Cited in HORUS ADR-008 as **considered cross-check candidate** for the orchestrated-baseline. **§203 elimination of cloud tiers**: Unstructured.io's commercial product (Serverless API, On-Prem hosted) routes Mandantendaten to their servers, which fails §203 StGB + §62a StBerG per `docs/sources/legal/stgb-203.md` + `docs/sources/legal/stberg-62a.md` + brainstorm v2 §7.6. **Only the OSS `unstructured` Python library (Apache 2.0, fully self-hosted) is admissible**.

Not chosen as the cross-check companion in ADR-008 — Unstructured is more commonly deployed as an *ingestion-for-RAG* preprocessor than as a key-value-extraction specialist; weaker H2 test instrument for the *orchestrated specialist* architectural class than MinerU pipeline backend. Preserved as fallback if both MinerU and PP-Structure encounter blockers (e.g., the Chinese-origin pretraining caveat proves load-bearing for German invoices).
