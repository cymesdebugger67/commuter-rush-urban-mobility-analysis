# Phase 01 — Official MTA source viability review

**Project owner and author:** Cyril James Lunzaga
**Review evidence:** Local Windows PowerShell terminal output supplied 2026-11-16; dataset `wujg-7c2s`

## Verified observations

- Isolated runtime: Python **3.14.10**; Python 3.11 launcher entry existed but pointed to an unavailable installation.
- Source-contract automated tests: **12 passed**.
- Official dataset metadata exposed all **11 required analytical fields**; the API metadata also exposed the point-type georeference field.
- Bounded live fare-row sample: **100 records**, **11 distinct station complexes**, **0 missing-coordinate records**, and **0 repeated station-hour/payment/fare keys** in that sample.
- Independent, complete fare-category extraction for one station-hour: station-complex ID `1`, **10 fare-category rows**, **2,364 estimated entries**, **156 included transfers**. Independent server sums and client sums reconciled.
- Raw sample and query responses were written under ignored `data/raw/`; the source audit manifest was written under ignored `outputs/source_probe/`.
- The research feature branch `feature/commuter-rush-research` was at baseline commit `b66708c`, with `commuter_rush/`, `docs/`, and `tests/` untracked. No research commit or push occurred during Phase 01.

## Decision and scope

**Phase 01: passed** for live access, schema availability, bounded reconciliation, and raw-data Git protection. This result does **not** verify October monthly completeness, station-hour stability, full-period payment-category behavior, analytical estimates, or any peak-hour story. Transfer amounts are already part of estimated ridership, not additional entries.

**Phase 02 authorization:** Run a bounded October 9 daily canary with independent daily `count(*)`, `sum(ridership)` and `sum(transfers)` reconciliation, then review the manifest before full month acquisition. Raw/processed source data stays local; only reviewed code, documentation, synthetic tests, and later curated aggregate portfolio artifacts may be versioned.
