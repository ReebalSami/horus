---
source_url: "https://www.mustangproject.org/zugferd/"
source_title: "Mustang Project — open-source ZUGFeRD generator/validator"
source_author: "Mustang Project (open-source)"
source_date: ""
retrieved_date: "2026-05-08"
extracted_concepts: []
tags: ["mustang-project", "zugferd", "synthetic-data", "pdf-generator", "data-unlock", "primary-tooling"]
archived_pdf: ""
status: stub
---

Mustang Project — open-source Java toolset for generating, validating, and parsing ZUGFeRD invoices (PDF/A-3 with embedded XML). Generates arbitrary ZUGFeRD-compliant PDFs from XML inputs. Cited in HORUS as a **primary tooling** (per brainstorm v2 §7.5): the "data unlock" that makes the thesis's evaluation loop feasible without manual labelling. Workflow: render ZUGFeRD PDF page → ask VLM to extract JSON → extract embedded XML ground truth → compare. Effectively unlimited synthetic supply with legal clarity (Mustang is open-source; ZUGFeRD is a public standard). Pairs with the public ZUGFeRD corpus (separate dataset stub) for real-world distribution checks.
