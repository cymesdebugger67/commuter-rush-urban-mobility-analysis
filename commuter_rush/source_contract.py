from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import json
import math
import os


DATASET_ID = "wujg-7c2s"
METADATA_URL = f"https://data.ny.gov/api/views/{DATASET_ID}.json"
RESOURCE_URL = f"https://data.ny.gov/resource/{DATASET_ID}.json"
STUDY_START = "2024-10-01T00:00:00"
STUDY_END = "2024-11-01T00:00:00"
PROBE_START = "2024-10-09T08:00:00"
PROBE_END = "2024-10-09T09:00:00"
REQUIRED_COLUMNS = frozenset({
    "transit_timestamp", "transit_mode", "station_complex_id", "station_complex",
    "borough", "payment_method", "fare_class_category", "ridership", "transfers",
    "latitude", "longitude",
})


class SourceContractError(ValueError):
    pass


def sha256_bytes(data):
    return sha256(data).hexdigest()


def metadata_contract(metadata):
    if not isinstance(metadata, dict):
        raise SourceContractError("Dataset metadata must be an object")
    if str(metadata.get("id")) != DATASET_ID:
        raise SourceContractError("Dataset identifier does not match the approved MTA source")
    columns = metadata.get("columns")
    if not isinstance(columns, list):
        raise SourceContractError("Source metadata does not expose columns")
    typed_columns = {}
    for column in columns:
        if not isinstance(column, dict):
            continue
        field = column.get("fieldName")
        if field and not str(field).startswith(":"):
            typed_columns[str(field)] = str(column.get("dataTypeName", "unknown"))
    missing = sorted(REQUIRED_COLUMNS - typed_columns.keys())
    if missing:
        raise SourceContractError(f"Source schema has changed: missing {missing}")
    return typed_columns


def parse_station_hour(value):
    if not isinstance(value, str):
        raise SourceContractError("Source timestamp must be a string")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SourceContractError(f"Invalid source timestamp: {value}") from exc
    if timestamp.tzinfo is not None:
        raise SourceContractError("Expected MTA source-local timestamp without UTC offset")
    if timestamp.minute != 0 or timestamp.second != 0 or timestamp.microsecond != 0:
        raise SourceContractError(f"Source timestamp is not hour-aligned: {value}")
    return timestamp


def nonnegative_decimal(value, field):
    if value is None or isinstance(value, bool):
        raise SourceContractError(f"{field} is missing or invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SourceContractError(f"{field} is not numeric: {value}") from exc
    if not number.is_finite() or number < 0:
        raise SourceContractError(f"{field} is negative or nonfinite")
    return number


def validate_records(rows, start=PROBE_START, end=PROBE_END):
    if not isinstance(rows, list) or not rows:
        raise SourceContractError("Source returned no rows for the requested hour")
    start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
    duplicate_keys = Counter()
    null_coordinate_rows = 0
    observed_boroughs = Counter()
    station_ids = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SourceContractError(f"Row {index} is not an object")
        missing = REQUIRED_COLUMNS - row.keys()
        if missing:
            raise SourceContractError(f"Row {index} has missing fields: {sorted(missing)}")
        timestamp = parse_station_hour(row["transit_timestamp"])
        if not start_dt <= timestamp < end_dt:
            raise SourceContractError(f"Row {index} lies outside the probe hour")
        if str(row["transit_mode"]).lower() != "subway":
            raise SourceContractError(f"Row {index} contains a non-subway observation")
        station_id = str(row["station_complex_id"]).strip()
        if not station_id or station_id.lower() == "none":
            raise SourceContractError(f"Row {index} has no station identifier")
        if not str(row["station_complex"] or "").strip():
            raise SourceContractError(f"Row {index} has no station label")
        borough = str(row["borough"] or "").strip()
        if not borough:
            raise SourceContractError(f"Row {index} has no borough")
        fare = str(row["fare_class_category"] or "").strip()
        method = str(row["payment_method"] or "").strip()
        if not fare or not method:
            raise SourceContractError(f"Row {index} lacks fare/payment identifiers")
        riders = nonnegative_decimal(row["ridership"], "ridership")
        transfers = nonnegative_decimal(row["transfers"], "transfers")
        if transfers > riders:
            raise SourceContractError(f"Row {index} transfers exceed ridership")
        latitude = row["latitude"]
        longitude = row["longitude"]
        if latitude in (None, "") or longitude in (None, ""):
            null_coordinate_rows += 1
        else:
            try:
                lat, lon = float(latitude), float(longitude)
            except (TypeError, ValueError) as exc:
                raise SourceContractError(f"Row {index} has invalid coordinates") from exc
            if not (math.isfinite(lat) and math.isfinite(lon) and 40 <= lat <= 41.2 and -75 <= lon <= -72.5):
                raise SourceContractError(f"Row {index} has implausible NYC coordinates")
        duplicate_keys[(row["transit_timestamp"], station_id, method, fare)] += 1
        observed_boroughs[borough] += 1
        station_ids.add(station_id)
    return {
        "sample_rows": len(rows),
        "sample_distinct_stations": len(station_ids),
        "boroughs_observed": dict(sorted(observed_boroughs.items())),
        "null_coordinate_rows": null_coordinate_rows,
        "repeated_station_hour_payment_fare_keys": sum(count - 1 for count in duplicate_keys.values() if count > 1),
    }


def reconcile_station_hour(rows, aggregate, station_id):
    if not isinstance(rows, list) or not rows:
        raise SourceContractError("No full-fare-category rows returned for station reconciliation")
    if len(rows) >= 1000:
        raise SourceContractError("Station fare extraction reached the safety limit of 1000 rows")
    validate_records(rows)
    if any(str(row["station_complex_id"]) != station_id for row in rows):
        raise SourceContractError("Station reconciliation contains another station")
    if not isinstance(aggregate, list) or len(aggregate) != 1:
        raise SourceContractError("Expected exactly one server-side station aggregate")
    server = aggregate[0]
    if str(server.get("station_complex_id")) != station_id:
        raise SourceContractError("Server aggregate station identifier mismatch")
    server_rows = int(nonnegative_decimal(server.get("fare_rows"), "fare_rows"))
    if server_rows != len(rows):
        raise SourceContractError("Source row-count reconciliation failed")
    client_riders = sum((nonnegative_decimal(row["ridership"], "ridership") for row in rows), Decimal(0))
    client_transfers = sum((nonnegative_decimal(row["transfers"], "transfers") for row in rows), Decimal(0))
    server_riders = nonnegative_decimal(server.get("estimated_entries"), "estimated_entries")
    server_transfers = nonnegative_decimal(server.get("included_transfers"), "included_transfers")
    if abs(client_riders - server_riders) > Decimal("0.00001"):
        raise SourceContractError("Source and local ridership sums do not reconcile")
    if abs(client_transfers - server_transfers) > Decimal("0.00001"):
        raise SourceContractError("Source and local transfer-subset sums do not reconcile")
    return {
        "station_complex_id": station_id,
        "fare_category_rows": len(rows),
        "estimated_station_hour_entries": str(server_riders),
        "included_transfer_subset": str(server_transfers),
        "source_to_client_reconciled": True,
    }


def write_json_atomic(path, content):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        temporary.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
