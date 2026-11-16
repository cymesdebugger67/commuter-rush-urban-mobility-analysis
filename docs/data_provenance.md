# Data provenance: MTA subway hourly ridership

## Source record

- **Source title:** MTA Subway Hourly Ridership: 2020–2024
- **Provider and underlying owner:** Metropolitan Transportation Authority (MTA)
- **Hosting catalog:** New York State Open Data
- **Dataset ID:** `wujg-7c2s`
- **Catalog:** https://data.ny.gov/d/wujg-7c2s
- **Metadata API:** https://data.ny.gov/api/views/wujg-7c2s.json
- **SODA API:** https://data.ny.gov/resource/wujg-7c2s.json
- **Catalog license field:** The license for this dataset is unspecified. Do not assert it is CC BY or any other specific license without further source evidence.
- **Use and attribution:** Attribute all derived results to the MTA and identify the exact source resource; review New York State Open Data portal terms for any further publication requirements.

## Source semantics

The MTA describes estimated fare-media entries by local hour, station complex, transit mode, payment method, and fare class. `transfers` is a subset of `ridership`. A station complex can include several platforms or routes. New York local clock timestamps have been rounded down to the hour. These records do not directly measure train load, trip length, platform crowding, or passengers' origins/destinations.

The metadata catalog currently exposes 12 public columns including `georeference`. The implementation treats **11 fields** as analytically required and does not depend on `georeference`, which duplicates coordinate meaning. Live field types and the actual hour sample must be confirmed by a user-executed probe; neither are claimed verified merely from this documentation.

## Verified October 2024 extraction and retention

**Author:** Cyril James Lunzaga

Study interval: 2024-10-01 00:00:00 inclusive through 2024-11-01 00:00:00 exclusive, in New York local time, filtered to `transit_mode='subway'`. The documented one-hour source probe, October 9 full-day canary, and all 31 daily acquisitions passed live MTA query reconciliation on 2026-11-16. The source-to-processed pipeline totals **2,466,181 fare-category rows**, **310,187 unique station-complex/hour observations**, **424 station complexes**, **744 observed clock hours**, and **114,680,137 estimated entries**. The transfer subset is 4,484,500 and is not added to entries.

The source sometimes reports different latitude/longitude values for the same station-complex ID and local hour. These variants are combined without changing summed entries, preserved in source audit JSON, and represented by a deterministic descriptive coordinate; **10,508 station-hours** showed coordinate variants. The source reports all 31 calendar days, but individual observed-hour station coverage ranges from **387–424 complexes**, not 424/424 everywhere. Missing station-hours are not filled with zero.

Each daily JSON snapshot and the processed CSV have a reproducible SHA-256 fingerprint; independent daily MTA server-side fare counts, estimated entries, and included transfers are reconciled. The verified processed CSV SHA-256 is `0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb` (25,797,208 bytes). Raw snapshots and the CSV are excluded from the public Git repository; source-linked curated summary tables and figures are retained under `portfolio/`.

## Limitations and rights

Historical MTA values may be revised; a later API extraction is not guaranteed to reproduce the exact 2026 snapshot fingerprint. The study cannot infer unique riders, origin–destination journeys, platform crowding, service delays, or long-run patterns. A catalog entry with an **unspecified license** does not authorize us to assert a particular Creative Commons license. Credit the MTA as data provider and consult the [MTA data guidance](https://www.mta.info/open-data) and [official dataset catalog](https://data.ny.gov/d/wujg-7c2s) before redistribution of the underlying raw dataset.

## Verification status

**Completed 2026-11-16:** Official schema, one-hour probe, corrected one-day canary, 31-day acquisition, source-to-client reconciliation, and 31 raw-file plus one processed-file fingerprint checks passed in the user's VS Code terminal. The reproducibility and code review remain subject to the separate final release gate.
