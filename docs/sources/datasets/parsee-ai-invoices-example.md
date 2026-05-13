---
source_url: "https://huggingface.co/datasets/parsee-ai/invoices-example"
source_title: "Parsee AI Invoices Example — bilingual (en+de) LLM-eval sample"
source_author: "Parsee AI"
source_date: "2024-03-20"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["parsee-ai", "invoices", "en-de", "bilingual", "llm-eval", "rag", "sample", "mit", "question-answering"]
archived_pdf: ""
status: stub
license_spdx: "MIT"
license_url: "https://huggingface.co/datasets/parsee-ai/invoices-example"
data_manifest: "data/raw/english/parsee-ai-invoices-example/MANIFEST.md"
acquisition_status: completed
---

Parsee AI Invoices Example — 45-row sample dataset (n<1K) generated from 15 publicly accessible invoice PDFs on app.parsee.ai. Designed for evaluating LLMs on RAG-style invoice question answering. Languages: English + German (en+de). Parquet format with columns: source_identifier, template_id, element_identifier, FEATURE_full_prompt, TRUTH_answer. Cited in HORUS as a **sanity-check sample for the Layer 3 analytical-query stage** (per brainstorm §9 amendment — parsee-ai/invoices-example, MIT license, en+de is unique among the candidate datasets). Value: tiny, MIT, bilingual, RAG/QA-oriented. Provides a minimal but real multilingual invoice-QA fixture for early Layer 3 eval smoke-testing before investing in a full custom en+de eval set.

- License: MIT
- Size: 45 rows, 42.7 KB parquet
- Languages: en, de
- Full eval methodology: https://github.com/parsee-ai/parsee-datasets/blob/main/datasets/invoices/parsee-loader/README.md
