# October 2024 subway entry patterns — descriptive findings

**Author:** Cyril James Lunzaga
**Data owner:** Metropolitan Transportation Authority (MTA)
**Source:** [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)
**Scope:** October 1–31, 2024, New York local clock time; subway station-complex hourly estimated entries

## Verified study footprint

- 310,187 unique station-hours across 424 complexes, 31 calendar days, and 744 observed clock hours.
- 114,680,137 estimated entries; the 4,484,500 transfer subset is already included and is not added to this total.
- 10,508 source station-hours had coordinate metadata variants; the acquisition retained an audit of both source-group values and the representative display coordinate.

## Descriptive demand structure

- Mean estimated entries per weekday: 4,128,696 (23 weekdays); mean per weekend day: 2,465,017 (8 weekend days). These are descriptive comparisons, not causal effects.
- Across weekdays, 07:00–09:59 contributes 22.88% and 16:00–18:59 contributes 25.84% of observed weekday estimated entries. Both windows have three clock hours per day.
- The highest mean systemwide weekday entry hour begins at 17:00, with 411,468 estimated entries per weekday on average.
- The 10 highest-volume station complexes contribute 18.71% of October estimated entries. Station-level entry Gini: 0.540.
- 424 station complexes pass the predefined >=90% observed-hour requirement in both peak windows; 0 are excluded from primary peak ranking, not from the systemwide entry totals.

## Interpretation and limits

Observed entries are modeled fare-paid station entries, not unique commuter trips, vehicle crowding, queue length, delay, or passenger origin-destination paths. A missing station-hour is not automatically zero. Day-type averages use each calendar day as an observation so a 23-weekday versus 8-weekend month does not inflate weekday hourly averages. We make no inference about long-run seasonality from one month. Station coordinates are representative display metadata with documented source inconsistencies; they are not authoritative geocoding.

All figures and tables are directly generated from the locally validated 2024-10 station-hour CSV. Inferential uncertainty and station clustering are reserved for separately reviewed later phases.
