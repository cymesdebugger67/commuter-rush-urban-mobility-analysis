# Station-hour data quality and release criteria

## Data completeness

The frozen window is October 2024, which contains 31 local calendar days and 744 local clock hours. Verify that each selected day is represented and all 24 daily hours appear in at least one station entry. Report the number of observed stations each hour. An absent station-hour is not equivalent to a zero-activity observation. No study-level completeness percentage based on an unverified fixed station inventory is permitted.

## Data accuracy

Require source-local, hour-aligned timestamps, station IDs and labels, finite nonnegative estimated entries and transfer-subset counts, transfers not exceeding entries, integer underlying fare-record counts, and plausible New York City coordinates when supplied. Preserve outliers until their source validity is assessed. Report missing coordinate rows instead of automatically inventing coordinates.

## Data consistency

The analysis grain is exactly `(transit_timestamp, station_complex_id)`. MTA source-grouped rows can repeat that key because coordinates or station names differ across underlying fare categories. After checking each source group, combine these groups by the stable station-hour key, retaining all source-grouped ridership, included transfers, and fare-row counts. Preserve all conflicting source-grouped rows and the selected metadata in the ignored daily snapshot, and independently reconcile summed totals against daily MTA controls. Choose one representative label/location deterministically using nonmissing coordinates, largest underlying fare-row count, largest estimated entries, and a lexical tie-break. This is a display convention, not proof of the actual station position. Conflicting borough assignments fail closed; repeated *identical* source grouping signatures fail as a possible pagination problem. Summarize name/coordinate variants and station IDs that vary over the month. Work only in the published source-local time convention.

## Data integrity

For each day, independently reconcile summed source fare-row counts, `ridership`, and `transfers` against an ungrouped Socrata scalar query using the same filter. Ensure a strict one-row-per-station-hour processed key. Store daily query URLs, response hashes, each affected source metadata variant, and individual daily snapshot hashes. Validate the recorded variant evidence again when reusing a daily cache. Fail closed on incomplete pagination, missing whole-clock hours, borough conflicts, unverifiable metadata audits, or reconciliation drift.

## Validation and signoff

Unit tests based on synthetic fixtures check guardrails; they are **not** observational findings. The live Phase 01 probe reconciled one station-hour. The first Phase 02 canary exposed an actual station-hour coordinate disagreement for station `601`; the 2026-11-16 diagnostic independently reconciled its two source metadata groups. The corrected implementation subsequently passed 33 unit tests and the live full-day canary; the complete 31-day October extraction, independent source-total reconciliations, and CSV/source-file hash audit passed on 2026-11-16. See `phase02_full_month_review.md` for the actual numeric evidence. Full acquisition success alone is not a claim of complete station-level coverage or universally stable metadata.

Every published result must cite the MTA dataset and its documented estimation limitations. The data page currently reports an unspecified dataset-specific license; do not assert a Creative Commons grant.
