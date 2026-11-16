# October 2024 acquisition — final source and quality review

- **Author:** Cyril James Lunzaga
- **Source owner:** Metropolitan Transportation Authority (MTA)
- **Source:** [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)
- **Evidence date:** 2026-11-16 (user-executed PowerShell output)

## Release decision

**Phase 02 acquisition and numerical QA: passed.** The official MTA API provided station-complex hourly estimated entries for the 31 local calendar days from 2024-10-01 inclusive to 2024-11-01 exclusive. The acquisition routine independently reconciled every daily total for source fare rows, estimated ridership and included transfers, retained all source-coordinate disagreements, and verified unique post-normalization station-hour keys. The user independently checked the processed CSV totals and all 31 source-file SHA-256 values.

| Acquisition metric | Verified value |
|---|---:|
| Local calendar days | 31 |
| Observed local clock hours | 744 |
| Unique station-hour observations | 310,187 |
| Distinct station complexes | 424 |
| Underlying fare-category records | 2,466,181 |
| Estimated subway station entries | 114,680,137 |
| Included transfers (subset of entries) | 4,484,500 |
| Source station-hours with coordinate variants | 10,508 |
| Source station-hours with name variants | 0 |
| Station complex IDs with changing representative metadata | 18 |
| Normalized rows lacking coordinates | 0 |
| Minimum/maximum reporting complexes per observed clock hour | 387 / 424 |

The independent processed-file SHA-256 is `0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb`; the processed CSV had 25,797,208 bytes. The validated acquisition manifest and all 31 raw source snapshots are retained locally and ignored by Git.

## Quality interpretation

**Completeness:** Each of the 31 days and 744 clock hours has at least one observed entry. This does not establish complete coverage of every station in every hour. The observed station count ranges from 387 to 424, and missing station-hours remain missing—not zeros. A station inventory of 424 observed at least once is not an official fixed daily denominator.

**Accuracy:** Estimated entries, included transfers, timestamps, counts, and coordinate bounds passed the source protocol's numerical checks. The source reports estimated fare-paid station entries, not directly observed unique commuter journeys or onboard train loads. Outliers have not yet been interpreted in the context of station-hours or station geography.

**Consistency:** Raw fare-group sums can contain different coordinates for the same station complex and hour. The final pipeline groups by station ID and local hour, preserves variant records in daily audit snapshots, and chooses a deterministic but non-authoritative representative coordinate for descriptive display. Across the month, 10,508 station-hours showed coordinate variants; this is a source-metadata issue, not 10,508 missing journeys. No source name-variant station-hours were found in the completed run.

**Integrity:** The post-aggregation CSV has 310,187 unique station-hour keys. Daily grouped totals and ungrouped independent source controls reconcile. Transfers are already part of `ridership` and were not added again. Fare-row counts reconcile to the 2,466,181 underlying source records.

**Validation:** A separate terminal audit verified 31 source snapshot hashes, CSV hash and byte count, date bounds, all 744 local clock hours, unique IDs, nonnegative counts, and exact source-manifest totals. All 33 unit tests passed before the live monthly run; unit fixtures are not treated as independent MTA findings.

## Analytical decision

The project may proceed to descriptive temporal and station-level analysis. The morning and evening windows remain fixed at 07:00–09:59 and 16:00–18:59 on weekdays, respectively. Analyses will disclose variable station-hour coverage, avoid imputing absent hours as zero, and refrain from using source coordinates as definitive station geocodes. Any inferential comparison or station typology must clear a separate Phase 04 methodology review.

The full dataset is historical and limited to one calendar month. Findings are not evidence of current subway utilization, congestion, train capacity, causal changes, or origin-destination travel.
