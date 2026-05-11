# notebooks/

Ad-hoc exploratory notebooks for HORUS.

## Important: this is NOT the experiment home

Per the `notebook-discipline` rule (`.windsurf/rules/notebook-discipline.md`),
**experiments live in `experiments/` as jupytext-paired `.py:percent` files**,
not here. `notebooks/` is the documented consumer exception for scratch /
exploration work that does not need papermill parameterisation.

Use `experiments/<slug>.py` for any hypothesis that will be reported in the
thesis. Use `notebooks/` only for throw-away EDA, API exploration, or
visualisation scratch work.

## Tracking status

Tracked. `.ipynb` files are universally gitignored (see `.gitignore`); only
the paired `.py:percent` sources are committed.

## Provenance

- `docs/prompts/stages/02-brainstorm.md` §8 step 1 ("exploratory work")
- `.windsurf/rules/notebook-discipline.md` clause 1 (consumer exception documented here)
- Issue #8: Repo structural prep (M2D.5 step 1)
