# Source feasibility protocol

## Purpose

Determine whether the officially published MTA resource `wujg-7c2s` supports a reproducible 2024 station-hour entry study. This is a **bounded pre-analysis audit**, not a complete monthly download or final quality signoff.

## Execution

From the repository root and isolated project Python environment (Python 3.14.10 verified):

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_source_contract.py' -v
& .\.venv\Scripts\python.exe -m commuter_rush.source_probe
```

No third-party package is required by these two commands. They rely on Python standard-library HTTP and test modules.

## Acceptance criteria

1. Metadata request must identify `wujg-7c2s` and include the 11 required analytical fields.
2. One fixed weekday morning station-hour must yield subway-mode fare-category records with hour-aligned local timestamps.
3. Source fields must have usable station IDs/names, borough and nonnegative entries/transfers; report missing coordinates and duplicated fare-category keys rather than silently repairing them.
4. A full-fare extraction for one observed station and hour must fit under the 1,000-record limit.
5. Independent Socrata `sum(ridership)`, `sum(transfers)` and `count(*)` must reconcile against client-side sums on the same rows.
6. Save bounded source responses under Git-ignored `data/raw/`, and a query/sha-256 audit under Git-ignored `outputs/source_probe/`.
7. On any contract failure, stop. Do not manufacture sample records, omit problematic fare classes, assume missing is zero, or infer monthly readiness.

## Next decision

After inspecting the actual output, choose a bounded full-October download plan (prefer server-side station-hour grouping with independent reconciliation), update the project log with genuine record counts, and freeze data preparation assumptions before generating research findings.

## Actual Phase 01 local signoff

The 2026-11-16 terminal output confirmed all 12 synthetic unit tests passed, a 100-row live MTA sample across 11 station IDs, and independent reconciliation of 10 source fare records to 2,364 estimated entries and 156 transfers for station-complex ID `1`. Full October coverage remains unverified. See `docs/phase01_source_review.md`.
