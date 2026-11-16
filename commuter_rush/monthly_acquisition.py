from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import json
import sys

from commuter_rush.source_contract import (
    DATASET_ID, METADATA_URL, SourceContractError, metadata_contract,
    sha256_bytes, write_json_atomic,
)
from commuter_rush.source_probe import fetch_json, query_url
from commuter_rush.monthly_quality import (
    dates_in_study, day_quality, normalize_grouped_row, summarize_month,
    write_month_csv_atomic, valid_decimal, integral_count, collapse_station_hour_variants,
)

PAGE_LIMIT = 5000
MAX_PAGES_PER_DAY = 6
CANARY_DATE = date(2024, 10, 9)
RAW_DIRECTORY = Path("data/raw/mta_october_2024")
OUTPUT_DIRECTORY = Path("outputs/monthly_acquisition")
PROCESSED_PATH = Path("data/processed/mta_subway_station_hour_october_2024.csv")
GROUP_FIELDS = ("transit_timestamp", "station_complex_id", "station_complex", "borough", "latitude", "longitude")
AGGREGATE_FIELDS = ",".join(GROUP_FIELDS) + ",sum(ridership) as estimated_entries,sum(transfers) as included_transfers,count(*) as fare_rows"


class MonthlyAcquisitionError(RuntimeError):
    pass


def stable_metadata_fingerprint(metadata, observed_schema):
    contract = {
        "dataset_id": metadata.get("id"),
        "updated_at": metadata.get("updatedAt"),
        "rows_updated_at": metadata.get("rowsUpdatedAt"),
        "columns": observed_schema,
    }
    return sha256_bytes(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def day_where(day):
    if day not in set(dates_in_study()):
        raise MonthlyAcquisitionError("Requested day outside frozen study window")
    tomorrow = day + timedelta(days=1)
    return (
        f"transit_timestamp >= '{day.isoformat()}T00:00:00' "
        f"AND transit_timestamp < '{tomorrow.isoformat()}T00:00:00' "
        "AND transit_mode = 'subway'"
    )


def grouped_query(day, offset):
    if offset < 0 or offset % PAGE_LIMIT:
        raise MonthlyAcquisitionError("Page offset must align to the fixed page size")
    return query_url({
        "$select": AGGREGATE_FIELDS,
        "$where": day_where(day),
        "$group": ",".join(GROUP_FIELDS),
        "$order": ",".join(f"{field} ASC" for field in GROUP_FIELDS),
        "$limit": PAGE_LIMIT,
        "$offset": offset,
    })


def control_query(day):
    return query_url({
        "$select": "count(*) as fare_rows,sum(ridership) as estimated_entries,sum(transfers) as included_transfers",
        "$where": day_where(day),
        "$limit": 1,
    })


def fetch_day(day, metadata_hash, fetch=fetch_json):
    aggregated = []
    page_logs = []
    for page_index in range(MAX_PAGES_PER_DAY):
        offset = PAGE_LIMIT * page_index
        url = grouped_query(day, offset)
        raw_rows, body_hash = fetch(url)
        if not isinstance(raw_rows, list):
            raise MonthlyAcquisitionError(f"Non-array response for grouped page {page_index}")
        if len(raw_rows) > PAGE_LIMIT:
            raise MonthlyAcquisitionError("API returned more than requested page limit")
        normalized = [normalize_grouped_row(r, day) for r in raw_rows]
        aggregated.extend(normalized)
        page_logs.append({"url": url, "response_sha256": body_hash, "rows": len(normalized)})
        if len(raw_rows) < PAGE_LIMIT:
            break
    else:
        raise MonthlyAcquisitionError("Day reached pagination safety cap: cannot confirm untruncated result")
    url = control_query(day)
    raw_control, control_hash = fetch(url)
    if not isinstance(raw_control, list) or len(raw_control) != 1:
        raise MonthlyAcquisitionError("Expected exactly one independent daily scalar control")
    scalar = raw_control[0]
    if not isinstance(scalar, dict):
        raise MonthlyAcquisitionError("Source daily control must be a mapping")
    control = {
        "fare_rows": integral_count(scalar.get("fare_rows"), "source fare_rows", 1),
        "estimated_entries": format(valid_decimal(scalar.get("estimated_entries"), "source entries"), "f"),
        "included_transfers": format(valid_decimal(scalar.get("included_transfers"), "source transfers"), "f"),
    }
    consolidated, metadata_conflicts = collapse_station_hour_variants(aggregated)
    quality = day_quality(consolidated, day, control, metadata_conflicts, len(aggregated))
    if quality["missing_clock_hours"]:
        raise MonthlyAcquisitionError(f"Daily source missing observed clock hours: {day}: {quality['missing_clock_hours']}")
    return {
        "schema_version": 2,
        "dataset_id": DATASET_ID,
        "date": day.isoformat(),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "metadata_sha256": metadata_hash,
        "where": day_where(day),
        "grouped_page_queries": page_logs,
        "independent_control_query": url,
        "independent_control_response_sha256": control_hash,
        "control": control,
        "quality": quality,
        "source_grouped_row_count": len(aggregated),
        "source_metadata_conflicts": metadata_conflicts,
        "rows": consolidated,
    }


def day_snapshot_path(day):
    return RAW_DIRECTORY / f"mta_subway_station_hour_{day.isoformat()}.json"


def load_verified_snapshot(path, day, metadata_hash):
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MonthlyAcquisitionError(f"Cannot resume invalid daily snapshot: {path}") from exc
    if snapshot.get("schema_version") != 2:
        raise MonthlyAcquisitionError("Legacy daily cache schema cannot validate source metadata conflicts")
    if snapshot.get("dataset_id") != DATASET_ID or snapshot.get("date") != day.isoformat():
        raise MonthlyAcquisitionError(f"Daily snapshot source/date mismatch: {path}")
    if snapshot.get("metadata_sha256") != metadata_hash:
        raise MonthlyAcquisitionError("Source metadata changed since prior snapshot. Review before mixing retrievals")
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        raise MonthlyAcquisitionError("Daily snapshot lacks grouped observations")
    if rows != [normalize_grouped_row(row, day) for row in rows]:
        raise MonthlyAcquisitionError("Daily snapshot normalized data has changed")
    observed_quality = day_quality(
        rows, day, snapshot.get("control"),
        snapshot.get("source_metadata_conflicts"), snapshot.get("source_grouped_row_count"),
    )
    if observed_quality != snapshot.get("quality") or observed_quality["missing_clock_hours"]:
        raise MonthlyAcquisitionError("Daily cached source reconciliation or coverage failed")
    if not isinstance(snapshot.get("grouped_page_queries"), list) or not snapshot["grouped_page_queries"]:
        raise MonthlyAcquisitionError("Daily snapshot missing source query audit")
    if not snapshot.get("independent_control_response_sha256"):
        raise MonthlyAcquisitionError("Daily snapshot missing independent source control audit")
    return snapshot


def file_digest(path):
    hash_value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hash_value.update(block)
    return {"path": str(path).replace("\\", "/"), "bytes": Path(path).stat().st_size, "sha256": hash_value.hexdigest()}


def run(mode, day=CANARY_DATE, fetch=fetch_json):
    if mode not in ("canary", "month"):
        raise MonthlyAcquisitionError("Mode must be canary or month")
    metadata, metadata_hash = fetch(METADATA_URL)
    observed_schema = metadata_contract(metadata)
    contract_hash = stable_metadata_fingerprint(metadata, observed_schema)
    expected_days = [day] if mode == "canary" else list(dates_in_study())
    daily_snapshots = []
    file_logs = []
    for index, target_day in enumerate(expected_days, start=1):
        path = day_snapshot_path(target_day)
        if path.exists():
            snapshot = load_verified_snapshot(path, target_day, contract_hash)
            action = "verified-cache"
        else:
            snapshot = fetch_day(target_day, contract_hash, fetch=fetch)
            write_json_atomic(path, snapshot)
            action = "downloaded"
        daily_snapshots.append(snapshot)
        file_logs.append(file_digest(path))
        q = snapshot["quality"]
        print(f"DAY {index:02d}/{len(expected_days):02d} {target_day}: {action}; station_hours={q['station_hour_rows']}; fare_rows={q['source_fare_rows']}; reconciled=True", flush=True)
    output = {
        "status": "canary_passed" if mode == "canary" else "month_acquisition_passed",
        "mode": mode,
        "dataset_id": DATASET_ID,
        "data_owner": "Metropolitan Transportation Authority",
        "data_source": "https://data.ny.gov/d/wujg-7c2s",
        "study_start_local_inclusive": "2024-10-01T00:00:00",
        "study_end_local_exclusive": "2024-11-01T00:00:00",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_metadata_sha256": metadata_hash,
        "source_metadata_contract_sha256": contract_hash,
        "source_metadata_updated_at": metadata.get("updatedAt"),
        "source_metadata_license": metadata.get("license"),
        "observed_source_fields": observed_schema,
        "daily_snapshot_files": file_logs,
        "days_completed": len(daily_snapshots),
        "days_expected": 31,
        "client_to_source_daily_controls_passed": True,
        "data_meaning": "Estimated subway station entries; transfers are a subset of ridership; zero not imputed for missing station-hours",
        "metadata_policy": "Collapse coordinate/name variants by station ID and hour after preserving and validating the source groups. Borough conflicts stop processing. Representative geometry is descriptive, not an authoritative station location.",
    }
    if mode == "canary":
        q = day_quality(
            daily_snapshots[0]["rows"], day, daily_snapshots[0]["control"],
            daily_snapshots[0]["source_metadata_conflicts"],
            daily_snapshots[0]["source_grouped_row_count"],
        )
        output["canary_quality"] = q
        output["decision_note"] = "One daily slice reconciled; full-month coverage and metadata consistency remain unverified"
    else:
        full_quality = summarize_month(daily_snapshots)
        csv_digest = write_month_csv_atomic(PROCESSED_PATH, daily_snapshots)
        output["month_quality"] = full_quality
        output["processed_csv"] = csv_digest
        output["decision_note"] = "Full-month aggregated source reconciling technically passed; analytical interpretation requires separate signoff"
        write_json_atomic(OUTPUT_DIRECTORY / "month_quality.json", full_quality)
    write_json_atomic(OUTPUT_DIRECTORY / "source_acquisition_manifest.json", output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded official MTA October 2024 station-hour acquisition")
    parser.add_argument("--mode", choices=("canary", "month"), required=True)
    parser.add_argument("--day", default="2024-10-09", help="Local day for the canary, YYYY-MM-DD")
    args = parser.parse_args(argv)
    try:
        day = date.fromisoformat(args.day)
        if args.mode == "month" and day != CANARY_DATE:
            raise MonthlyAcquisitionError("Month mode does not accept a custom day")
        result = run(args.mode, day)
    except (MonthlyAcquisitionError, SourceContractError, ValueError, KeyError, OSError, TypeError) as exc:
        print(f"STOP - MTA monthly source acquisition not verified: {exc}", file=sys.stderr)
        return 2
    print(f"PASS - {result['status']}: {result['days_completed']} days; independent source controls reconciled")
    if args.mode == "month":
        q = result["month_quality"]
        print(f"PASS - Observed {q['observed_clock_hours']} local clock hours; {q['station_hour_rows']} station-hour records")
        print(f"QA - Station-hours with source metadata variants: {q['station_hours_with_multiple_source_metadata']}")
        print(f"PASS - Source fare-row count reconciled: {q['source_fare_rows_reconciled']}")
        print(f"PASS - Processed CSV SHA256: {result['processed_csv']['sha256']}")
    else:
        q = result["canary_quality"]
        print(f"QA - Preserved source metadata conflicts: {q['station_hours_with_multiple_source_metadata']}")
        print(f"QA - Coordinate disagreements: {q['station_hours_with_coordinate_variants']}")
        print("SCOPE - One-day canary only; month-wide acquisition requires separate --mode month")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
