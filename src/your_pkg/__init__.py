"""your_pkg — bootstrapped from python-ml-uv L3 template.

POST-BOOTSTRAP RENAME REQUIRED. The scaffold uses two placeholder tokens:

  - `your-pkg`  (kebab-case) — for `pyproject.toml` `[project] name`
  - `your_pkg`  (snake_case) — for the directory + Python imports

Mirrors real PyPI projects' kebab/snake split (e.g., `scikit-learn` (PyPI)
→ `sklearn` (import name)).

Steps:
  1. Rename `src/your_pkg/` to `src/<your_snake_slug>/`.
  2. Update `pyproject.toml` `name = "your-pkg"` to your kebab slug.
  3. Update `tests/test_smoke.py` + module docstrings (sed-replace `your_pkg`).
  4. Run `make install && make test` to confirm.

A future `/start-project` enhancement will automate the sed-substitution.
See `cascade-system/queue/pending-review.md` for the L1-promotion entry.
"""

__version__ = "0.1.0"
