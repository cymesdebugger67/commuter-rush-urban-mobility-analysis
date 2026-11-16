# Phase 02 station-hour metadata conflict review

**Research owner:** Cyril James Lunzaga
**Source:** Metropolitan Transportation Authority, [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)
**Diagnostic date:** 2026-11-16
**Observation:** 2024-10-09 00:00–00:59, New York source-local time; station-complex ID `601`

## Confirmed source observation

The first live day extraction stopped on a repeated `(transit_timestamp, station_complex_id)` key. The focused terminal diagnostic independently queried (1) raw fare-category records, (2) source-grouped station/location aggregates, and (3) an independent scalar `count(*)`, `sum(ridership)`, `sum(transfers)` under the same source filters. All three reconciled.

| Source metadata variant | Station label | Borough | Latitude | Longitude | Fare rows | Estimated entries | Included transfers |
|---|---|---|---:|---:|---:|---:|---:|
| A | 14 St (F,M,1,2,3)/6 Av (L) | Manhattan | 40.737827 | -73.99679 | 1 | 2 | 0 |
| B | 14 St (F,M,1,2,3)/6 Av (L) | Manhattan | 40.738228 | -73.99621 | 9 | 284 | 4 |
| **Total** | | | | | **10** | **286** | **4** |

The diagnostic observed 10 distinct payment/fare-category keys, no repeated fare-category keys, two grouped metadata records, and identical station ID, name, and borough. The only evidenced disagreement was coordinates. The metadata variation is **not** justification to remove the small variant or to treat the two groups as two different station-hour observations.

## Frozen correction and limitations

1. Keep the authoritative analytical key as station-complex ID plus local hour.
2. Sum **only** the separated source groups' estimated entries, included transfers, and underlying fare-row counts. Transfers are already a subset of entries and must not be added to entries.
3. Preserve affected original source-grouped records, representative metadata, and the exact source-control audit inside ignored daily snapshots; expose conflict counts in the quality report.
4. Choose the display name/location deterministically: prefer nonmissing coordinate pairs, then more underlying fare records, then more estimated entries, then lexical order. The coordinate chosen for this observed station-hour would be `(40.738228, -73.99621)`; this is **not** an assertion that the alternate source coordinate is incorrect or that the chosen point is geographically authoritative.
5. Stop rather than infer a borough when the same station-hour has conflicting borough assignments. Reject repeated identical full metadata groups, which might reflect pagination problems.
6. Require independent full-day source-control reconciliation, complete 24-hour canary coverage, and audit revalidation on cached daily data. These requirements were satisfied in the live canary and 31-day October run on 2026-11-16; the completed acquisition and monthly audit are documented in `phase02_full_month_review.md`.

The fix is an empirically motivated **data preparation decision**, not a research result about commuting demand. The source group's station-level coordinates should be treated as approximate plotting coordinates, and meaningful spatial interpretations require a subsequent location-quality review.
