# Phase 04 — Statistical evidence and station entry profiles

**Author:** Cyril James Lunzaga

## Research decisions

The reference population is the source-recorded October 2024 subway station-hour estimates, not a probability sample of all future commuter activity. Resampling below is exploratory **within-month stability** rather than a 95% prediction interval or proof of causal day-type effects. Station-hours share calendar-day conditions and must not be treated as 310,187 independent experimental units.

1. **Calendar-day demand:** Compare the mean of the 23 recorded weekdays with the mean of the eight weekend dates. Report mean difference, mean ratio, and percentile intervals from 10,000 independent bootstrap draws *within each day-type group*. The sample unit is a whole day.
2. **Paired weekday rush-hour contrast:** For each of the 23 weekdays, compute the share of that day's entries occurring at 07:00–09:59 and 16:00–18:59, using the same daily denominator. Summarize evening-minus-morning percentage points; resample complete weekday pairs, not individual station-hours.
3. **Borough orientation:** Compute these paired daily differences separately for Manhattan, Brooklyn, Queens, and the Bronx. Each borough's denominator is its own observed daily weekday entries. Compare Manhattan's daily difference with the aggregate of the other three boroughs on the *same day*. Report percentile bootstrap intervals from complete paired days.
4. **Station temporal profiles:** Classify each station complex using the balance index `(evening_entries - morning_entries) / (evening_entries + morning_entries)` across recorded weekdays. Values above +0.15 are `evening-oriented`, below -0.15 are `morning-oriented`, and the remainder are `balanced`. This is a transparent rule-based descriptive typology, **not learned or validated commuter origin/destination labels**.
5. **Completeness gate:** Station typology requires at least 90% observed station-hours in *both* compared windows; an unreported hour is not zero. Stations with undefined ratios are `not_eligible`.
6. **Sensitivity:** Recompute the orientation using equally long windows 06:00–09:59 and 15:00–18:59, and report the percentage retaining the same category among stations eligible under both sets of windows. This choice is a convention, not a search for maximum agreement.

## Numerical reproducibility

- Source: MTA `wujg-7c2s`, October 2024, station complex × local clock hour.
- Source CSV fingerprint: `0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb`.
- Bootstrap: deterministic `numpy.random.default_rng` seed `202410` with 10,000 percentile replicates.
- Analyses use the existing validated source loader and do not re-download data.
- The transfer subset remains included in estimated entries and must not be added again.
- Interval endpoints describe day-to-day sampling sensitivity within this particular month. No formal population-level or policy causal inference is claimed. Statistical procedures do not automatically correct for temporal serial dependence, holidays, weather, or system-service differences.

## Outputs

The statistical module writes five evidence tables and a JSON summary. The station-profile module writes two typology tables and a JSON summary. The visualization module renders three additional figures with a file-hash manifest. All new tables and figures are generated from the verified monthly CSV or the module's source-linked outputs. A release review must check that charts show the right units and sample sizes before they are referenced in the README.
