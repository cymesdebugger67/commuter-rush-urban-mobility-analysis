# The Commuter Rush: research plan

**Author:** Cyril James Lunzaga
**Domain:** Urban mobility and transit operations
**Current phase:** 06 — Final release QA pending after Phases 00–05 numerical and methodological reviews (2026-11-16)

## Research problem

Subway demand is uneven across hours, days, station complexes, and boroughs. Examining the timing and concentration of fare-paid station entries can identify demand patterns without claiming direct measurements of train crowding or end-to-end passenger journeys.

## Unit of analysis and boundaries

The intended cleaned observation is one **subway station complex × New York local hour**, after a verified sum across non-overlapping payment/fare categories. The source observation is finer-grained: hour × transit mode × station complex × payment method × fare category. Transfers are already included in ridership and are not added to it. The frozen study is **2024-10-01 00:00 inclusive through 2024-11-01 00:00 exclusive**, local New York time, subway mode only. The 31-day source acquisition passed all source-control, hash, and time-coverage checks on 2026-11-16. The month precedes the November 2024 daylight-saving transition, avoiding duplicated clock hours within this provisional window.

## Research questions

1. What are the daily and hourly distributions of estimated entries across subway station complexes?
2. How concentrated are weekday morning and evening entries across complexes and boroughs?
3. How do normalized hourly profiles vary between weekdays and weekends, and between stations?
4. Are observed differences robust to alternative hour windows, sample-coverage rules, and extreme values?
5. Do transparent station peak-orientation categories remain stable under alternative, equal-length rush windows?

## Frozen analytical conventions

- Weekday morning peak: hours **07, 08, 09** (local clock hours).
- Weekday evening peak: hours **16, 17, 18**.
- Weekend: Saturday and Sunday in the local calendar.
- Primary outcome: **estimated entries**, not riders on board, trips, capacity utilization, service delays, or congestion.
- Primary descriptions: station-hour totals, day types, boroughs, station shares, and peak-to-off-peak contrasts.
- First statistical option: resampling calendar days and reporting uncertainty, rather than treating each station-hour as an independent sample.
- Approved final method: a rule-based station orientation index and alternative-window stability analysis; no clustering is claimed.

## Quality and validity gates

- **Completeness:** time coverage, station-hour coverage, missing fields, explicit separation of missing from observed zero.
- **Accuracy:** parse timestamps, confirm nonnegative and finite counts, check coordinate plausibility and extreme values without automatic deletion.
- **Consistency:** stable station IDs/names, payment labels, geographic attributes, local-day classification and units.
- **Integrity:** unique post-aggregation station-hour keys, no joined duplication, no double-counted fares or transfer subset.
- **Validation:** source-field contract, independent client-to-server aggregation reconciliation, repeatable hashes, tests, and date-bound checks.

## Major exclusions and limitations

The project will not claim direct commuter journeys, crowding, platform conditions, train frequency, delays, causal policy effects, or representativeness of passengers beyond the defined tap/swipe estimation process. A single month cannot establish seasonality or long-run trends. Station coordinates are descriptive map locations, not measures of passengers' origins and destinations. Missing source records must never be assigned zero ridership without a reason supported by the data producer.

## Decision gates

1. **Source feasibility:** live schema, reachable query, fare fields, date scope and independent aggregation reconciliation.
2. **Monthly acquisition:** bounded full-window query or auditable alternative with recorded row counts and SHA-256.
3. **Analytical readiness:** completeness and reconciliation thresholds reviewed before inferential comparisons.
4. **Evidence and methods:** descriptive plots precede optional statistical tests or clustering.
5. **Publication:** owner-only byline, full source attribution, interpretable visuals, reproducible commands, truthful limitations, final Git audit.

The October data acquisition, source QA, descriptive figures, within-month day-resampling statistics, and rule-based station typology were reviewed through Phase 04. The October 14 exclusion check passed Phase 05. Publication still requires executed-notebook, artifact-integrity, Git/security and final README review; no machine-learning clustering was used.

## Phase 01 source viability decision (2026-11-16)

Official MTA schema and actual subway fare-category records verified. A 100-row sample covered 11 station complexes. One independently reconciled station-hour had 10 fare-category records, 2,364 estimated entries, and 156 transfers already included in ridership; 12 source-contract tests passed. This was a preliminary station-hour probe. The full October acquisition subsequently passed Phase 02 quality validation; see `phase02_full_month_review.md`.

## Phase 02 monthly acquisition decision (2026-11-16)

Full month source and integrity review passed with 310,187 station-hours, 424 distinct complexes, 114,680,137 estimated entries, 4,484,500 included transfers and 2,466,181 fare records. All 744 local clock hours appear, although station reporting varies by hour (387–424). Exactly 10,508 station-hour coordinate source variations were audited and reconciled. The `phase02_full_month_review.md` documents exact checks, restrictions, file hashes, and the decision to proceed to descriptive EDA.
