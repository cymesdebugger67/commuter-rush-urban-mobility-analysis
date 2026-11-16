from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import csv
import hashlib
import json
import math
import os

from commuter_rush.source_contract import SourceContractError, nonnegative_decimal, parse_station_hour


STUDY_START_DATE = date(2024, 10, 1)
STUDY_END_DATE = date(2024, 11, 1)
ANALYTICAL_FIELDS = (
    "transit_timestamp", "station_complex_id", "station_complex", "borough",
    "latitude", "longitude", "estimated_entries", "included_transfers", "fare_rows",
)


def dates_in_study():
    day = STUDY_START_DATE
    while day < STUDY_END_DATE:
        yield day
        day += timedelta(days=1)


def valid_decimal(value, name):
    return nonnegative_decimal(value, name)


def integral_count(value, name, minimum=0):
    number = valid_decimal(value, name)
    if number != number.to_integral_value() or number < minimum:
        raise SourceContractError(f"{name} is not an integer >= {minimum}")
    return int(number)


def normalized_decimal(value, name):
    number = valid_decimal(value, name)
    return format(number, "f")


def normalize_grouped_row(row, expected_day):
    required = set(ANALYTICAL_FIELDS)
    if not isinstance(row, dict) or required - row.keys():
        raise SourceContractError(f"Grouped row has missing fields: {sorted(required - set(row)) if isinstance(row, dict) else 'not a mapping'}")
    hour = parse_station_hour(row["transit_timestamp"])
    if hour.date() != expected_day:
        raise SourceContractError("Grouped timestamp outside requested day")
    station_id = str(row["station_complex_id"] or "").strip()
    station_name = str(row["station_complex"] or "").strip()
    borough = str(row["borough"] or "").strip()
    if not station_id or not station_name or not borough:
        raise SourceContractError("Missing station identifier, name, or borough")
    latitude, longitude = row["latitude"], row["longitude"]
    if (latitude in (None, "")) != (longitude in (None, "")):
        raise SourceContractError("Only one of the location coordinates is missing")
    if latitude not in (None, ""):
        try:
            lat = float(latitude)
            lon = float(longitude)
        except (ValueError, TypeError) as exc:
            raise SourceContractError("Location coordinates are invalid") from exc
        if not (math.isfinite(lat) and math.isfinite(lon) and 40 <= lat <= 41.2 and -75 <= lon <= -72.5):
            raise SourceContractError("Station coordinates outside plausible NYC bounds")
    entries = valid_decimal(row["estimated_entries"], "estimated_entries")
    transfers = valid_decimal(row["included_transfers"], "included_transfers")
    if transfers > entries:
        raise SourceContractError("Transfers exceed estimated entries")
    fare_rows = integral_count(row["fare_rows"], "fare_rows", minimum=1)
    return {
        "transit_timestamp": hour.strftime("%Y-%m-%dT%H:00:00"),
        "station_complex_id": station_id,
        "station_complex": station_name,
        "borough": borough,
        "latitude": "" if latitude in (None, "") else normalized_decimal(latitude, "latitude"),
        "longitude": "" if longitude in (None, "") else "-" + normalized_decimal(abs(Decimal(str(longitude))), "longitude"),
        "estimated_entries": format(entries, "f"),
        "included_transfers": format(transfers, "f"),
        "fare_rows": fare_rows,
    }



def collapse_station_hour_variants(source_rows):
    if not isinstance(source_rows, list) or not source_rows:
        raise SourceContractError("No source grouped rows to collapse")
    by_station_hour = defaultdict(list)
    seen_source_groups = set()
    for row in source_rows:
        if not isinstance(row, dict) or set(ANALYTICAL_FIELDS) - row.keys():
            raise SourceContractError("Source grouped row missing analytical fields")
        key = (row["transit_timestamp"], row["station_complex_id"])
        signature = key + (row["station_complex"], row["borough"], row["latitude"], row["longitude"])
        if signature in seen_source_groups:
            raise SourceContractError(f"Repeated identical source metadata group: {key}")
        seen_source_groups.add(signature)
        by_station_hour[key].append(row)
    collapsed = []
    conflicts = []
    for key, variants in sorted(by_station_hour.items()):
        boroughs = {row["borough"] for row in variants}
        if len(boroughs) != 1:
            raise SourceContractError(f"Station-hour has conflicting borough assignments: {key}")
        choice = sorted(
            variants,
            key=lambda r: (
                -int(r["latitude"] != "" and r["longitude"] != ""),
                -integral_count(r["fare_rows"], "fare_rows", minimum=1),
                -valid_decimal(r["estimated_entries"], "estimated_entries"),
                r["station_complex"], r["latitude"], r["longitude"],
            ),
        )[0]
        entries = sum((valid_decimal(r["estimated_entries"], "estimated_entries") for r in variants), Decimal(0))
        transfers = sum((valid_decimal(r["included_transfers"], "included_transfers") for r in variants), Decimal(0))
        if transfers > entries:
            raise SourceContractError(f"Transfers exceed entries in station-hour: {key}")
        fares = sum(integral_count(r["fare_rows"], "fare_rows", minimum=1) for r in variants)
        combined = dict(choice)
        combined["estimated_entries"] = format(entries, "f")
        combined["included_transfers"] = format(transfers, "f")
        combined["fare_rows"] = fares
        collapsed.append(combined)
        if len(variants) > 1:
            conflicts.append({
                "transit_timestamp": key[0],
                "station_complex_id": key[1],
                "source_group_count": len(variants),
                "distinct_station_names": len({r["station_complex"] for r in variants}),
                "distinct_coordinate_pairs": len({(r["latitude"], r["longitude"]) for r in variants}),
                "selection_rule": "nonmissing_coordinates_then_fare_row_count_then_entries_then_lexical",
                "chosen_station_metadata": {
                    field: choice[field] for field in ("station_complex", "borough", "latitude", "longitude")
                },
                "source_variant_rows": sorted(
                    variants,
                    key=lambda r: (r["station_complex"], r["latitude"], r["longitude"]),
                ),
            })
    return collapsed, conflicts


def validate_metadata_audit(rows, conflicts, source_grouped_row_count):
    if not isinstance(conflicts, list):
        raise SourceContractError("Metadata conflict audit must be a list")
    known = {(r["transit_timestamp"], r["station_complex_id"]): r for r in rows}
    audited = set()
    excess = 0
    for event in conflicts:
        if not isinstance(event, dict):
            raise SourceContractError("Invalid metadata audit event")
        key = (event.get("transit_timestamp"), event.get("station_complex_id"))
        if key in audited or key not in known:
            raise SourceContractError(f"Duplicate or unknown metadata conflict audit: {key}")
        audited.add(key)
        variants = event.get("source_variant_rows")
        if not isinstance(variants, list) or len(variants) < 2:
            raise SourceContractError("Metadata conflict audit needs at least two source variants")
        if any((r.get("transit_timestamp"), r.get("station_complex_id")) != key for r in variants):
            raise SourceContractError("Metadata audit includes an unrelated station-hour")
        restored, recorded = collapse_station_hour_variants(variants)
        if len(restored) != 1 or restored[0] != known[key] or recorded != [event]:
            raise SourceContractError("Cached metadata conflict audit differs from published station-hour")
        excess += len(variants) - 1
    expected_source_count = len(rows) + excess
    if integral_count(source_grouped_row_count, "source_grouped_row_count") != expected_source_count:
        raise SourceContractError("Source grouped row count differs from metadata conflict audit")
    return {
        "source_grouped_metadata_rows": expected_source_count,
        "station_hours_with_multiple_source_metadata": len(conflicts),
        "source_metadata_rows_collapsed": excess,
        "station_hours_with_coordinate_variants": sum(
            event["distinct_coordinate_pairs"] > 1 for event in conflicts
        ),
        "station_hours_with_name_variants": sum(
            event["distinct_station_names"] > 1 for event in conflicts
        ),
        "source_metadata_conflicts_preserved": True,
    }


def day_quality(rows, expected_day, scalar, metadata_conflicts=None, source_grouped_row_count=None):
    if not isinstance(rows, list) or not rows:
        raise SourceContractError(f"No grouped observations for {expected_day}")
    keys = set()
    hours = set()
    stations = set()
    observed_meta = defaultdict(set)
    coordinate_missing = 0
    entry_total = Decimal(0)
    transfer_total = Decimal(0)
    fare_count = 0
    for item in rows:
        hour = parse_station_hour(item["transit_timestamp"])
        if hour.date() != expected_day:
            raise SourceContractError("Grouped records contain another date")
        key = (item["transit_timestamp"], item["station_complex_id"])
        if key in keys:
            raise SourceContractError(f"Repeated station-hour: {key}")
        keys.add(key)
        hours.add(hour.hour)
        stations.add(item["station_complex_id"])
        observed_meta[item["station_complex_id"]].add((item["station_complex"], item["borough"], item["latitude"], item["longitude"]))
        coordinate_missing += int(item["latitude"] == "")
        entry_total += valid_decimal(item["estimated_entries"], "estimated_entries")
        transfer_total += valid_decimal(item["included_transfers"], "included_transfers")
        fare_count += integral_count(item["fare_rows"], "fare_rows", minimum=1)
    if not isinstance(scalar, dict):
        raise SourceContractError("Missing independent source scalar")
    source_fares = integral_count(scalar.get("fare_rows"), "source fare_rows", minimum=1)
    source_entries = valid_decimal(scalar.get("estimated_entries"), "source estimated_entries")
    source_transfers = valid_decimal(scalar.get("included_transfers"), "source included_transfers")
    for actual, reference, label in (
        (fare_count, source_fares, "source fare-row count"),
        (entry_total, source_entries, "estimated entries"),
        (transfer_total, source_transfers, "included transfers"),
    ):
        if abs(Decimal(actual) - Decimal(reference)) > Decimal("0.00001"):
            raise SourceContractError(f"Daily {label} does not reconcile")
    if metadata_conflicts is None:
        metadata_conflicts = []
    if source_grouped_row_count is None:
        source_grouped_row_count = len(rows)
    audit_summary = validate_metadata_audit(rows, metadata_conflicts, source_grouped_row_count)
    return {
        "date": expected_day.isoformat(),
        **audit_summary,
        "station_hour_rows": len(rows),
        "source_fare_rows": fare_count,
        "estimated_entries": format(entry_total, "f"),
        "included_transfers": format(transfer_total, "f"),
        "observed_hour_count": len(hours),
        "missing_clock_hours": sorted(set(range(24)) - hours),
        "distinct_stations": len(stations),
        "station_hour_keys_unique": True,
        "missing_coordinate_rows": coordinate_missing,
        "within_day_station_metadata_conflicts": sum(len(m) > 1 for m in observed_meta.values()),
        "independent_source_totals_reconciled": True,
    }


def summarize_month(day_snapshots):
    expected_days = {d.isoformat() for d in dates_in_study()}
    supplied_days = {d["date"] for d in day_snapshots}
    if len(supplied_days) != len(day_snapshots) or not supplied_days <= expected_days:
        raise SourceContractError("Unexpected or repeated study dates")
    if supplied_days != expected_days:
        raise SourceContractError(f"Month incomplete: {len(expected_days - supplied_days)} days missing")
    total_entries = Decimal(0)
    total_transfers = Decimal(0)
    source_fares = 0
    total_rows = 0
    hour_keys = set()
    station_meta = defaultdict(set)
    hour_counts = Counter()
    stations = set()
    coordinates_missing = 0
    daily_summary = []
    metadata_source_rows = 0
    metadata_conflict_hours = 0
    metadata_coordinate_hours = 0
    metadata_name_hours = 0
    for snapshot in sorted(day_snapshots, key=lambda entry: entry["date"]):
        current_day = date.fromisoformat(snapshot["date"])
        q = day_quality(
            snapshot["rows"], current_day, snapshot["control"],
            snapshot.get("source_metadata_conflicts"), snapshot.get("source_grouped_row_count"),
        )
        if q["missing_clock_hours"]:
            raise SourceContractError(f"No records for clock hours: {snapshot['date']}: {q['missing_clock_hours']}")
        daily_summary.append(q)
        metadata_source_rows += q["source_grouped_metadata_rows"]
        metadata_conflict_hours += q["station_hours_with_multiple_source_metadata"]
        metadata_coordinate_hours += q["station_hours_with_coordinate_variants"]
        metadata_name_hours += q["station_hours_with_name_variants"]
        total_entries += Decimal(q["estimated_entries"])
        total_transfers += Decimal(q["included_transfers"])
        source_fares += q["source_fare_rows"]
        total_rows += q["station_hour_rows"]
        coordinates_missing += q["missing_coordinate_rows"]
        for row in snapshot["rows"]:
            key = (row["transit_timestamp"], row["station_complex_id"])
            if key in hour_keys:
                raise SourceContractError(f"Duplicate month-wide station-hour: {key}")
            hour_keys.add(key)
            station_id = row["station_complex_id"]
            stations.add(station_id)
            station_meta[station_id].add((row["station_complex"], row["borough"], row["latitude"], row["longitude"]))
            hour_counts[row["transit_timestamp"]] += 1
    expected_hour_count = len(expected_days) * 24
    if len(hour_counts) != expected_hour_count:
        raise SourceContractError(f"Expected {expected_hour_count} observed hours; found {len(hour_counts)}")
    return {
        "days": len(daily_summary),
        "observed_clock_hours": len(hour_counts),
        "expected_clock_hours_in_study_month": expected_hour_count,
        "station_hour_rows": total_rows,
        "source_grouped_metadata_rows": metadata_source_rows,
        "station_hours_with_multiple_source_metadata": metadata_conflict_hours,
        "station_hours_with_coordinate_variants": metadata_coordinate_hours,
        "station_hours_with_name_variants": metadata_name_hours,
        "source_metadata_conflicts_preserved": True,
        "unique_station_complexes": len(stations),
        "source_fare_rows_reconciled": source_fares,
        "estimated_entries": format(total_entries, "f"),
        "included_transfers_subset": format(total_transfers, "f"),
        "missing_coordinate_rows": coordinates_missing,
        "station_ids_with_multiple_metadata_variants": sum(len(v) > 1 for v in station_meta.values()),
        "minimum_stations_in_observed_hour": min(hour_counts.values()),
        "maximum_stations_in_observed_hour": max(hour_counts.values()),
        "daily_summary": daily_summary,
        "all_daily_source_controls_reconciled": True,
        "station_hour_keys_unique": True,
        "missing_station_hours_not_assumed_zero": True,
    }


def write_month_csv_atomic(destination, snapshots):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    digest = hashlib.sha256()
    try:
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ANALYTICAL_FIELDS, lineterminator="\n")
            writer.writeheader()
            for snapshot in sorted(snapshots, key=lambda item: item["date"]):
                writer.writerows(sorted(snapshot["rows"], key=lambda r: (r["transit_timestamp"], r["station_complex_id"])))
        with tmp.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"path": str(path).replace("\\", "/"), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}
