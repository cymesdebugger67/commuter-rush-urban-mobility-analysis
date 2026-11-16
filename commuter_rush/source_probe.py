from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import time

from commuter_rush.source_contract import (
    DATASET_ID, METADATA_URL, RESOURCE_URL, PROBE_START, PROBE_END,
    SourceContractError, metadata_contract, reconcile_station_hour,
    sha256_bytes, validate_records, write_json_atomic,
)


SOURCE_FIELDS = (
    "transit_timestamp", "transit_mode", "station_complex_id", "station_complex",
    "borough", "payment_method", "fare_class_category", "ridership",
    "transfers", "latitude", "longitude",
)
MAX_BODY_BYTES = 6_000_000


class ProbeError(RuntimeError):
    pass


def fetch_json(url):
    last_error = None
    for attempt in range(2):
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": "CommuterRushDataResearch/1.0"})
            with urlopen(request, timeout=45) as response:
                data = response.read(MAX_BODY_BYTES + 1)
                if len(data) > MAX_BODY_BYTES:
                    raise ProbeError("API response exceeds 6 MB safety bound")
                return json.loads(data), sha256_bytes(data)
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.reason}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"Connection error: {exc}"
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProbeError(f"API returned invalid JSON: {exc}") from exc
        if attempt == 0:
            time.sleep(2)
    raise ProbeError(f"Request failed for {url}: {last_error}")


def query_url(parameters):
    return f"{RESOURCE_URL}?{urlencode(parameters)}"


def bound_where(extra=None):
    where = (
        f"transit_timestamp >= '{PROBE_START}' "
        f"AND transit_timestamp < '{PROBE_END}' "
        "AND transit_mode = 'subway'"
    )
    return f"{where} AND {extra}" if extra else where


def station_literal(station_id):
    return "'" + station_id.replace("'", "''") + "'"


def run():
    metadata, metadata_hash = fetch_json(METADATA_URL)
    columns = metadata_contract(metadata)
    sample_query = query_url({
        "$select": ",".join(SOURCE_FIELDS),
        "$where": bound_where(),
        "$order": "station_complex_id ASC,payment_method ASC,fare_class_category ASC",
        "$limit": 100,
    })
    sample, sample_hash = fetch_json(sample_query)
    sample_quality = validate_records(sample)
    station_id = str(sample[0]["station_complex_id"])
    station_filter = f"station_complex_id = {station_literal(station_id)}"
    station_query = query_url({
        "$select": ",".join(SOURCE_FIELDS),
        "$where": bound_where(station_filter),
        "$order": "payment_method ASC,fare_class_category ASC",
        "$limit": 1000,
    })
    station_rows, station_hash = fetch_json(station_query)
    aggregate_query = query_url({
        "$select": "station_complex_id,count(*) as fare_rows,sum(ridership) as estimated_entries,sum(transfers) as included_transfers",
        "$where": bound_where(station_filter),
        "$group": "station_complex_id",
        "$limit": 2,
    })
    server_aggregate, aggregate_hash = fetch_json(aggregate_query)
    reconciliation = reconcile_station_hour(station_rows, server_aggregate, station_id)
    capture_time = datetime.now(timezone.utc).isoformat()
    write_json_atomic("data/raw/mta_probe_station_fares.json", station_rows)
    write_json_atomic("data/raw/mta_probe_sample.json", sample)
    write_json_atomic("data/raw/mta_probe_server_aggregate.json", server_aggregate)
    output = {
        "status": "passed_with_observations" if sample_quality["repeated_station_hour_payment_fare_keys"] else "passed",
        "dataset_id": DATASET_ID,
        "data_owner": "Metropolitan Transportation Authority",
        "captured_at_utc": capture_time,
        "metadata_url": METADATA_URL,
        "metadata_sha256": metadata_hash,
        "source_metadata_updated_at": metadata.get("updatedAt"),
        "dataset_license_in_metadata": metadata.get("license"),
        "observed_source_columns_and_types": columns,
        "probe_start_nyc_local": PROBE_START,
        "probe_end_nyc_local": PROBE_END,
        "sample_query_url": sample_query,
        "sample_raw_response_sha256": sample_hash,
        "sample_quality": sample_quality,
        "station_fares_query_url": station_query,
        "station_fares_raw_response_sha256": station_hash,
        "server_aggregate_query_url": aggregate_query,
        "server_aggregate_raw_response_sha256": aggregate_hash,
        "independent_station_hour_reconciliation": reconciliation,
        "interpretation": "Hourly estimated station entries; transfers already included in ridership; not trips or measured crowding",
        "scope": "One weekday station-hour source feasibility only; not an October-wide study",
    }
    write_json_atomic("outputs/source_probe/source_feasibility.json", output)
    return output


def main():
    try:
        result = run()
    except (SourceContractError, ProbeError, ValueError, KeyError) as exc:
        print(f"STOP - MTA source feasibility not verified: {exc}")
        raise SystemExit(2) from exc
    print("PASS - Official MTA schema contains all 11 required analytical fields")
    print(f"PASS - Hourly subway fare records observed: {result['sample_quality']['sample_rows']}")
    print(f"PASS - Client/server fare aggregation reconciled: {result['independent_station_hour_reconciliation']['station_complex_id']}")
    print("PASS - Raw query responses stored locally under ignored data/raw")
    print("PASS - Provenance and probe manifest written under ignored outputs/source_probe")
    print("SCOPE - This tests one station-hour only; monthly coverage remains unverified")


if __name__ == "__main__":
    main()
