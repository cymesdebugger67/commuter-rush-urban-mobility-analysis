# Phase 03 numerical and visual review

**Author:** Cyril James Lunzaga
**Study:** The Commuter Rush — Urban Mobility Analytics
**Review date:** 2026-11-16

The source-verified October 2024 dataset contains 310,187 station-hours, 424 station complexes, and 114,680,137 estimated subway entries. Phase 03 numerical QA passed 46 tests, all ten table fingerprints, six figure fingerprints, and the report fingerprint. The review archive `phase03_verified_review_bundle.zip` had SHA-256 `25572cc53fbd3b1a842b68c9b618523c16f945921678eb199453db1cdc0fb79d`.

### Observations

- Weekdays comprise 23 of 31 dates. The three-hour morning and evening periods respectively contribute 22.8761% and 25.8434% of weekday estimated entries.
- The highest mean weekday entry hour begins at 17:00 New York local time.
- The ten largest complexes contribute 18.7129% of total October entries; descriptive station-total Gini is 0.5398.
- Manhattan's weekday evening window contributes 31.72% of borough weekday entries versus 16.50% for the morning; Queens, the Bronx, and Brooklyn exhibit larger morning than evening entry shares.
- Chart titles, axes, scales, and source caveats were inspected using the actual six PNG figures, not only their hashes.

### Presentation improvement

The borough peak-share figure's legend overlaps the Bronx morning bar in the original Phase 03 render. Phase 04 corrects the legend placement without changing numerical results. Long station names on the highest-volume bar chart are abbreviated for readability; full labels remain available in the associated station table.

### Analytical boundaries

These are estimated station entries rather than unique commuter trips, origins/destinations, crowding, delays, or capacity use. Counts are from one historical month. Source coordinate variants were audited and do not establish precise entrance locations. Complete system hour coverage does not imply every station reported every hour. Missing station-hours were not replaced with zeros.

Visual release signoff requires confirming that the revised borough chart no longer covers its bars. Phase 04 statistical results remain subject to genuine-data execution and separate QA.
