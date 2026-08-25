# notebooks/

Ad-hoc exploratory notebooks for HORUS.

## Important: this is NOT the experiment home

Per the project's notebook discipline,
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

- Issue #8: repo structural prep
