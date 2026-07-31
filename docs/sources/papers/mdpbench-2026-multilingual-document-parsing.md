---
source_url: "https://arxiv.org/abs/2603.28130"
source_title: "MDPBench: Multilingual Document Parsing Benchmark"
source_date: "2026-03"
retrieved_date: "2026-07-31"
extracted_concepts: []
tags: ["mdpbench", "multilingual", "document-parsing", "benchmark", "photographed-documents", "robustness", "adr-054"]
archived_pdf: ""
status: stub
---

MDPBench — Multilingual Document Parsing Benchmark (March 2026): 17 languages, 3,400 images.
Headline finding relevant to HORUS: **open-source parsers drop ~17.8 % on photographed documents**
(and ~14 % on non-Latin scripts) while closed-source models stay robust. Cited in ADR-054 as the
real-world honesty caveat: the HORUS ZUGFeRD corpus is born-digital PDF renders, so bake-off
answerability numbers will not transfer 1:1 to camera-scanned Belege; the degraded/photographed
robustness axis is explicitly descoped to the thesis future-work chapter (scope freeze). First
surfaced in `docs/prompts/stages/02-brainstorm.md` §9.2 (claude-chat-missed new finds).
