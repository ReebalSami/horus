---
source_url: "https://github.com/ZUGFeRD/corpus"
source_title: "ZUGFeRD corpus — public collection of ZUGFeRD invoices"
source_author: "ZUGFeRD project / FeRD (Forum elektronische Rechnung Deutschland)"
source_date: "2025-09-03"
retrieved_date: "2026-05-13"
extracted_concepts: []
tags: ["zugferd", "dataset", "german-invoices", "public", "primary-corpus", "data-unlock", "apache-2.0"]
archived_pdf: ""
status: stub
license_spdx: "Apache-2.0"
license_url: "https://github.com/ZUGFeRD/corpus/blob/master/LICENSE"
data_manifest: "data/raw/german/zugferd-corpus/MANIFEST.md"
acquisition_status: completed
---

ZUGFeRD corpus — publicly hosted collection of ZUGFeRD-format invoices (PDF/A-3 with embedded XML ground truth) maintained by the ZUGFeRD project on GitHub. Cited in HORUS as a **primary evaluation dataset** (per brainstorm v2 §7.5 + §15 Datasets). The embedded XML provides the ground truth for the extraction-evaluation loop without manual labelling: render PDF page → ask VLM to extract JSON → extract embedded XML → compare. Pairs with the Mustang Project tool (synthetic generation, see `docs/sources/tools/mustang-project.md`) and the GI 2021 paper (real-world distribution check, see `docs/sources/papers/gi-2021-german-invoices.md`). Licence + size + per-format breakdown to be confirmed at deep-read or first-experiment evaluation milestone.
