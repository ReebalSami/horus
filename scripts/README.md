# scripts/

One-off and reusable utility scripts for HORUS.

## Tracking status

Tracked. Scripts here are committed as ordinary Python files (no jupytext
pairing required).

## Canonical contents

```
scripts/
├── generate_zugferd_smoke.py   # ADR-005 smoke: factur-x bind + self-check
├── validate_zugferd.py          # ADR-005 cross-tool: Mustang Java validator wrapper
├── dataset_prep/                # dataset download helpers, format conversions (future)
└── utils/                       # shared utilities reused across scripts (future)
```

### ADR-005 ZUGFeRD smoke (issue #9)

End-to-end one-shot: `make zugferd-smoke`. Runs:

1. `generate_zugferd_smoke.py` — generates a single Factur-X 1.08 MINIMUM-profile invoice via `factur-x.generate_from_file` with a hand-authored CII XML literal + a `pypdf` blank PDF. Self-checks via factur-x's built-in XSD + Schematron. Output: `data/raw/smoke/invoice-001.pdf` (gitignored).
2. `validate_zugferd.py` — invokes the Mustang Project (Java, `tools/mustangproject/Mustang-CLI-*.jar`) via subprocess for an **independent cross-tool** validation. Parses Mustang's XML verdict; exits 0 if `<summary status="valid"/>`, 1 if invalid, 2 if execution failed.

Prerequisites: `make install` (factur-x via uv) + `make mustang-jar` (one-time Mustang JAR fetch). See ADR-005 for the full dual-track rationale.

The first ZUGFeRD XML-extraction-from-PDF helper (brainstorm §8 step 3-4) is scoped to the **next** issue alongside the script-architecture ADR.

Scripts that grow into a reusable library component are graduated to `src/horus/` via a standard refactor + ADR.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §8 step 1-2
- Issue #8: Repo structural prep (M2D.5 step 1)
- Issue #9: ADR-005 + synthetic-invoice generator install (M2D.5 step 2) — the scripts listed above
- Issue #15 (forthcoming): XML-extraction script + script-architecture ADR (M2D.5 step 3)
