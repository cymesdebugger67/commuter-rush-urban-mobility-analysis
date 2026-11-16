# Phase 06 — Release readiness protocol

**Author:** Cyril James Lunzaga

## Approved research baseline

The source-verified October 2024 station-hour research has 31 observed dates, 744 local hours, 424 station complexes, 310,187 unique station-hour observations, 2,466,181 underlying fare-category source rows, and 114,680,137 estimated entries. The user-reported collection and complete Phase 05A run passed 69 unit tests, including the 2024-10-14 sensitivity check. The corresponding upload `phase05_review_bundle.zip` was independently opened and its SHA-256 verified as `382b837697365f4e3ecb1390d9b6558c9de2786e3ba25118b27efe2f2eaf6235`.

Phase 04 numerical and nine-chart visual signoff was previously approved with methodological limits. The current work fixes the unrelated bike-sharing root scaffold, presents an original cover, updates stale milestone/provenance text, improves dependency declarations and pandas timedelta compatibility, adds a direct notebook execution checker and a repeatable local release audit. The release must not overwrite or distribute the original downloaded CSV and source snapshots.

## Final local validation, in order

1. Verify branch `feature/commuter-rush-research`, remote origin and the frozen source CSV SHA-256 before installing any release files.
2. Apply the guarded source/document patch, preserving backups of every replaced file and of `docs/project_log.md`.
3. Install declared project requirements into `.venv` and run `python -W error::DeprecationWarning -m unittest discover -s tests -p 'test_*.py' -q`. Absence of project-specific deprecated timedelta warnings is required.
4. Regenerate descriptive figures with `python -m commuter_rush.temporal_visuals`, which updates its figure-hash manifest. The underlying numerical tables remain unchanged.
5. Run `python -m commuter_rush.notebook_check` against the real processed CSV. This executes six trusted code cells in a Python terminal; it **does not claim to execute an interactive Jupyter kernel**.
6. Run `python -m commuter_rush.release_audit`. This checks source and artifact fingerprints, notebook execution evidence, README attribution, and candidate Git paths/obvious secrets. It does not modify Git or assert permission to redistribute source records.
7. Inspect the README and corrected figures in VS Code or GitHub preview. Record any actual legibility issues before publishing.

## Controlled Git release gate

Never use `git add .` blindly or force-push. Inspect the complete status and candidate paths. Stage only intentionally reviewed code, docs, notebook, curated tables, figures, and cover. Check `git diff --cached --check`, `git diff --cached --stat`, a staged names list, and the staged README/requirements/source changes. Confirm that `data/raw`, `data/processed`, `outputs`, `.venv`, review ZIPs, tokens, and unrelated notebook artifacts are absent. Then commit on the feature branch, push it, and review the resulting remote branch. Merge into `main` in a controlled separate step after approval, without force changes.

## Source attribution and permission caveat

Official MTA [dataset `wujg-7c2s`](https://data.ny.gov/d/wujg-7c2s), New York State Open Data. The dataset catalog's **license is unspecified**. This repository publishes independent code and derived summary analyses with attribution, not raw source records or the processed monthly CSV. The public-data listing alone must not be described as a particular redistribution license. Confirm any additional publisher terms before distributing raw records.

## Research limits

Source entries do not count unique riders, whole journeys, train occupancy, exits, capacity or congestion. The 10,508 coordinate-variant station-hours are auditable and not evidence of multiple station complexes. Not all 424 stations report each of the 744 hours; missing was never imputed as zero. Single-month day-resampling intervals do not establish long-term certainty or effects of service/weather policies. The October 14 sensitivity date is excluded only in a documented alternative calculation. The rule-based station orientation is not machine-learning clustering.

**Publication status:** Not yet released; local installation, notebook evidence, final Git review, and public README preview remain pending until the user reports their terminal results.
