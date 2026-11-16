# Project milestones and decision log

**Project:** The Commuter Rush — Urban Mobility Analytics
**Author:** Cyril James Lunzaga
**Implementation workflow:** Author-written, terminal-executed Python; actual results reviewed before moving phases.

| Phase | Objective | Status | Evidence / decision | Next action |
|---|---|---|---|---|
| 00 | Git foundation and baseline | passed | Initial commit `b66708c` pushed to `origin/main`; local `feature/commuter-rush-research` created and reported clean | Source feasibility |
| 01 | MTA source contract and bounded probe | passed | 2026-11-16: 12 synthetic tests, live 100-record sample, 11 stations, one independent source/client station-hour reconciliation (10 fare rows, 2,364 entries, 156 transfer subset); see `phase01_source_review.md` | Monthly canary |
| 02 | October extraction and data quality | passed | 2026-11-16: Corrected Oct 9 canary passed (10,077 station-hours, 4,359,386 entries, 326 coordinate-variant station-hours). Full October extraction passed: 31 days, 744 hours, 310,187 station-hours, 424 complexes, 114,680,137 estimated entries, 2,466,181 fare records, all daily source controls and 31 file hashes reconciled. See `phase02_full_month_review.md` | Descriptive EDA |
| 03 | Descriptive temporal and borough analysis | passed | Genuine October figures, 10 tables and first report numerically and visually reviewed | Statistical evidence |
| 04 | Statistical evidence and station orientation | passed | 58 tests; 17 tables, 9 figures and 2 reports; day-level bootstrap and 424 station classifications reviewed | Sensitivity and notebook |
| 05 | October 14 sensitivity and case-study notebook | passed_numerical | 69 tests; sensitivity reconciled, notebook delivered, user review ZIP verified | Execute notebook and release QA |
| 06 | Release integration and GitHub preparation | in_review | Final README, cover, dependency cleanup and release checks installed; publication not yet approved | Final test, stage and Git review |

## Dated decisions

- **2026-11-16:** Selected this research as an independent intermediate-to-advanced transit demand case study; no Codex. Public authorship belongs solely to Cyril James Lunzaga.
- **2026-11-16:** Verified initial Git baseline `b66708c`, published `main`, and created local research branch `feature/commuter-rush-research`. These actions are complete; no research implementation had been committed at that checkpoint.
- **2026-11-16:** Provisionally selected October 2024 and station-complex hourly estimated subway entries. Selected a bounded live source probe before any full-month extraction. Source API feasibility and quality outcomes remain unverified until executed.

- **2026-11-16:** Phase 01 live validation passed using Python 3.14.10; all 12 tests passed; sample 100 fare rows from 11 stations; station-complex ID `1` reconciled 10 fare records, 2,364 estimated entries, and 156 transfers as a subset. No full-October results claimed.
- **2026-11-16:** The initial Phase 02 live Oct 9 canary detected repeated key `(2024-10-09T00:00:00, 601)` because the two source groups have different coordinates. The targeted MTA raw/group/control diagnostic confirmed 10 fare rows (1 and 9), 286 estimated entries (2 and 284), and 4 included transfers with no repeated fare-category key; the three totals reconciled independently. The first diagnostic failed due to an omitted selected field (`transit_mode`); this was corrected in the terminal without changing research modules.
- **2026-11-16:** Approved conservative source metadata policy: consolidate by station ID/hour, preserve source coordinate conflicts, use a deterministic descriptive coordinate, stop on borough conflicts and duplicate grouping signatures, and reconcile independent daily controls. The patch passed all 33 automated tests and the live Oct 9 canary; station 601 retained 286 entries and 4 included transfers.
- **2026-11-16:** Full October acquisition and terminal quality audit passed: 31 days, 744 source-local hours, 310,187 station-hours, 424 station complexes, 114,680,137 estimated entries, 4,484,500 included transfers, and 2,466,181 underlying fare records. All 31 source snapshots and the 25,797,208-byte CSV passed fingerprint verification. 10,508 coordinate-variant station-hours were preserved in source audits; no observed hour was imputed. Phase 02 passed; no Git research commit or push yet.
- **2026-11-16:** Phase 03 descriptive implementation prepared after Phase 02 approval. The analysis and figure code passed 46 synthetic/unit tests locally (including legacy acquisition tests); this does **not** constitute a reviewed live-data analytical result. Actual results and image signoff are pending local execution.

## Operating rules

Record only observed outcomes, unresolved blockers, and approved scope changes. Treat tests using synthetic fixtures as implementation assurance, not as proof of real-world findings. Record each data collection query and checksum. Do not modify the frozen study window after examining results without documenting its reason and downstream effects. Do not make Git commits or push during the initial source-probe checkpoint.

## Phase 04 statistical checkpoint (2026-11-16)

- Status: Numerical verification passed; visual review pending.
- Source: October 2024 MTA station-hour data, 310,187 records and 424 station complexes.
- Statistical review: Calendar-day bootstrap intervals and paired weekday borough comparisons.
- Station profiles: 424 eligible complexes; alternative-window stability 88.91509433962264%.
- Testing: Complete automated suite passed.
- Artifacts: 17 curated tables, 9 figures, and 2 findings reports verified.
- Next: Visual signoff, notebook integration, README, and controlled Git review.


## Phase 06 release integration (2026-11-16)

- Phase 05 sensitivity passed: 1.674916 weekday/weekend ratio; 1.693806 excluding October 14.
- Corrected numerical parser and source lookup retained in the research implementation.
- Phase 06 release files installed; source CSV and raw MTA snapshots were not modified.
- Final notebook execution, artifact verification and GitHub publication remain pending.
