---
source_url: "https://docs.python.org/3/reference/import.html"
source_title: "5. The import system — Python 3.14 documentation"
source_author: "Python Software Foundation"
source_date: ""
retrieved_date: "2026-05-23"
extracted_concepts: []
tags: ["python", "packaging", "imports", "sys-path"]
archived_pdf: ""
status: stub
---

<!--
Canonical reference for Python's import system. Cited by ADR-022 (`scripts/`
directory status) as the authoritative source for how Python resolves package
imports vs script-direct invocation.

Key facts pertinent to ADR-022:

- A directory becomes a *regular package* when it contains an `__init__.py`
  (even an empty one). Regular packages are importable as a single name via
  `import <pkg>` once `<pkg>`'s parent directory is on `sys.path`.
- A directory without `__init__.py` may still be importable as an *implicit
  namespace package* (PEP 420) under specific conditions, but the standard
  recommendation for first-party project code is the explicit `__init__.py`
  form.
- When a script is invoked via direct path (`python scripts/foo.py`), Python
  prepends the script's own directory to `sys.path[0]` — NOT the repo root.
  Sibling imports via `from scripts import bar` therefore require the repo
  root to be added to `sys.path` manually (e.g., via
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`).
- When the same script is invoked as a module (`python -m scripts.foo`),
  Python adds the current working directory to `sys.path[0]`; if invoked from
  the repo root, `from scripts import bar` then works without manual sys.path
  manipulation.

See also: PEP 328 (Imports: Multi-Line and Absolute/Relative), PEP 420
(Implicit Namespace Packages), PEP 8 (Style Guide for Python Code).
-->
