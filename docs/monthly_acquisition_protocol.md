# October 2024 source acquisition protocol

**Research owner:** Cyril James Lunzaga
**Source:** Metropolitan Transportation Authority, [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)
**Study period:** 2024-10-01 inclusive to 2024-11-01 exclusive, source-local New York timestamps
**Source API:** `https://data.ny.gov/resource/wujg-7c2s.json`

## Unit of observation and collection design

The raw MTA source is subdivided by station complex, hour, payment method, and fare class. This project requests server-side groups by local hour, station-complex ID, station name, borough, latitude, and longitude, summing `ridership` and `transfers` separately and recording `count(*)` of underlying fare-category records. It does **not** add transfers to ridership: they are already included within ridership.

Each day is independently filtered to subway-mode observations in a half-open time range. Grouped pages use a fixed 5,000-row limit, consistent sort order, and offsets. Up to six pages per day are permitted; hitting that cap fails closed rather than accepting possibly truncated data. Each day also requests an **independent** source-side ungrouped `count(*)`, `sum(ridership)`, and `sum(transfers)` using the exact same day/mode filter. Source-grouped rows may repeat a station-hour because individual fare categories carry different station coordinates or names. Normalize and validate the source groups, then consolidate to the unique `(transit_timestamp, station_complex_id)` analysis grain while preserving all original conflicting grouped records in an audited daily snapshot. The representative name and coordinates are selected deterministically from the source groups (prefer populated coordinates, more underlying fare rows, larger entry totals, then lexical tie-break) solely for descriptive presentation. Borough disagreements, repeated identical source-group signatures, and unexplained source-control differences stop acquisition. Report the frequency of coordinate/name variants; do not portray a chosen coordinate as an authoritative geocoding resolution. The consolidated page sums must match the independent source controls. Any missing local clock hour, invalid station identifier, nonfinite or negative count, implausible coordinate, or mismatch stops acquisition for that day.

The Phase 02 snapshot schema is version 2 and preserves source-group metadata conflict evidence; existing schema-version-1 daily caches are not silently accepted. This correction follows the live station `601` diagnostic described in `phase02_metadata_conflict_review.md`.

The source is accessed publicly, without credentials. Requests have bounded response sizes, timeouts, and limited retry behavior inherited from the Phase 01 source probe. Transient API failures may occur. Successful days are written atomically under the Git-ignored `data/raw/mta_october_2024/` directory, with their source-query URLs and response hashes; a subsequent run validates and reuses them. The cached day's stable source-contract fingerprint must match the current metadata fingerprint. The metadata raw response hash is also recorded in the run manifest; volatile metadata fields are not used to invalidate the semantic contract.

## Terminal execution

From the project root, using the isolated environment executable:

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -m unittest discover -s tests -p 'test_*.py' -v
& $py -m commuter_rush.monthly_acquisition --mode canary
```

Review the canary's source manifest and actual daily coverage before attempting the full month. The canary runs only on **October 9, 2024**, a weekday selected before viewing analytical results. Once approved, execute:

```powershell
& $py -m commuter_rush.monthly_acquisition --mode month
```

The month command processes October 1–31, reuses a verified canary snapshot, and produces an ignored `data/processed/mta_subway_station_hour_october_2024.csv`, `outputs/monthly_acquisition/source_acquisition_manifest.json`, and `outputs/monthly_acquisition/month_quality.json`. The manifest contains daily raw-file hashes, grouped-count reconciliation evidence, the processed-file SHA-256, source details, and observed coverage diagnostics.

If the monthly command fails partway, do not delete successful daily snapshots. Inspect the reported blocker, then resume using the same command only after the problem is understood. Do not treat partial downloaded data as a complete study.

## Analytical restrictions

No observed station-hour is interpreted as a rider journey, a train load, an origin-to-destination trip, measured crowding, or a service-reliability measure. The source reports estimated entries. An absent station-hour is **missing**, not automatically zero. We require all 744 October local clock hours to appear somewhere in the dataset; the project does not assume every station must report every hour. Station metadata changes, station-hour coverage variation, fare-category semantics, and extreme values require explicit review after acquisition. The study month has no daylight-saving clock change, but the source-local time convention must remain unchanged.

No code or results should be published to `main` before analyst review of the full monthly quality evidence.
