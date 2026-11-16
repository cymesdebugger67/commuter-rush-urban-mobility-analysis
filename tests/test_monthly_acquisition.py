import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from commuter_rush import monthly_acquisition as acquire
from commuter_rush.source_contract import REQUIRED_COLUMNS, SourceContractError


def metadata():
    return {"id": acquire.DATASET_ID, "updatedAt": 123, "rowsUpdatedAt": 122, "columns": [
        {"fieldName": name, "dataTypeName": "text"} for name in REQUIRED_COLUMNS
    ]}


def sample_group(day, hour):
    return {
        "transit_timestamp": f"{day}T{hour:02d}:00:00.000", "station_complex_id": "100",
        "station_complex": "Synthetic Center", "borough": "Manhattan", "latitude": "40.71",
        "longitude": "-73.98", "estimated_entries": "8", "included_transfers": "2", "fare_rows": "3",
    }


def fake_fetch(url):
    if url == acquire.METADATA_URL:
        return metadata(), "synthetic_metadata_hash"
    params = parse_qs(urlparse(url).query)
    where = params["$where"][0]
    day = where.split("'")[1][:10]
    if "$group" in params:
        offset = int(params["$offset"][0])
        return ([sample_group(day, hr) for hr in range(24)] if offset == 0 else []), "synthetic_page_hash"
    if "count(*)" in params["$select"][0]:
        return ([{"fare_rows": "72", "estimated_entries": "192", "included_transfers": "48"}]), "synthetic_control_hash"
    raise AssertionError(f"Unexpected test query: {url}")


class MonthlyAcquisitionTests(unittest.TestCase):
    def test_queries_frozen_and_ordered(self):
        url = acquire.grouped_query(date(2024, 10, 9), 0)
        self.assertIn("2024-10-09T00%3A00%3A00", url)
        self.assertIn("%24group=", url)
        self.assertIn("%24order=", url)
        self.assertIn("%24limit=5000", url)
        self.assertIn("%24offset=0", url)
        with self.assertRaises(acquire.MonthlyAcquisitionError):
            acquire.grouped_query(date(2024, 11, 1), 0)
        with self.assertRaises(acquire.MonthlyAcquisitionError):
            acquire.grouped_query(date(2024, 10, 9), 10)

    def test_day_fetch_reconciles_independently(self):
        result = acquire.fetch_day(date(2024, 10, 9), "hash", fetch=fake_fetch)
        self.assertEqual(result["quality"]["station_hour_rows"], 24)
        self.assertEqual(result["quality"]["source_fare_rows"], 72)
        self.assertEqual(result["quality"]["observed_hour_count"], 24)
        self.assertEqual(result["quality"]["estimated_entries"], "192")

    def test_missing_hour_rejected_at_canary(self):
        def missing_hour_fetch(url):
            payload, digest = fake_fetch(url)
            params = parse_qs(urlparse(url).query)
            if "$group" in params:
                return payload[:-1], digest
            if url != acquire.METADATA_URL:
                return [{"fare_rows": "69", "estimated_entries": "184", "included_transfers": "46"}], digest
            return payload, digest
        with self.assertRaises(acquire.MonthlyAcquisitionError):
            acquire.fetch_day(date(2024, 10, 9), "hash", fetch=missing_hour_fetch)

    def test_fare_sum_mismatch_rejected(self):
        def altered_control_fetch(url):
            payload, digest = fake_fetch(url)
            if "$group" not in parse_qs(urlparse(url).query) and url != acquire.METADATA_URL:
                return [{**payload[0], "estimated_entries": "193"}], digest
            return payload, digest
        with self.assertRaises(SourceContractError):
            acquire.fetch_day(date(2024, 10, 9), "hash", fetch=altered_control_fetch)

    def test_canary_file_reuse_and_metadata_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(acquire, "RAW_DIRECTORY", Path(folder) / "raw"), patch.object(acquire, "OUTPUT_DIRECTORY", Path(folder) / "out"):
                first = acquire.run("canary", fetch=fake_fetch)
                self.assertEqual(first["status"], "canary_passed")
                source_path = acquire.day_snapshot_path(date(2024, 10, 9))
                second = acquire.run("canary", fetch=fake_fetch)
                self.assertEqual(second["daily_snapshot_files"][0]["sha256"], first["daily_snapshot_files"][0]["sha256"])
                cached = json.loads(source_path.read_text(encoding="utf-8"))
                cached["control"]["estimated_entries"] = "500"
                source_path.write_text(json.dumps(cached), encoding="utf-8")
                with self.assertRaises(SourceContractError):
                    acquire.run("canary", fetch=fake_fetch)

    def test_live_style_coordinate_conflict_is_collapsed_and_audited(self):
        def station_coordinate_conflict_fetch(url):
            if url == acquire.METADATA_URL:
                return metadata(), "synthetic_conflict_metadata"
            params = parse_qs(urlparse(url).query)
            if "$group" in params:
                day = params["$where"][0].split("'")[1][:10]
                rows = [sample_group(day, hour) for hour in range(24)]
                rows[0] = {**rows[0], "station_complex_id": "601", "latitude": "40.737827", "longitude": "-73.99679", "fare_rows": "1", "estimated_entries": "2", "included_transfers": "0"}
                rows.insert(1, {**rows[0], "latitude": "40.738228", "longitude": "-73.99621", "fare_rows": "9", "estimated_entries": "284", "included_transfers": "4"})
                return rows, "synthetic_conflict_page"
            if "count(*)" in params["$select"][0]:
                return [{"fare_rows": "79", "estimated_entries": "470", "included_transfers": "50"}], "synthetic_control"
            raise AssertionError("Unexpected query")
        snapshot = acquire.fetch_day(date(2024, 10, 9), "synthetic_contract", fetch=station_coordinate_conflict_fetch)
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(snapshot["source_grouped_row_count"], 25)
        self.assertEqual(snapshot["quality"]["station_hour_rows"], 24)
        self.assertEqual(snapshot["quality"]["station_hours_with_coordinate_variants"], 1)
        self.assertEqual(snapshot["quality"]["estimated_entries"], "470")
        self.assertEqual(snapshot["quality"]["source_fare_rows"], 79)
        self.assertEqual(len(snapshot["source_metadata_conflicts"]), 1)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(acquire, "RAW_DIRECTORY", Path(folder) / "raw"), patch.object(acquire, "OUTPUT_DIRECTORY", Path(folder) / "out"):
                first = acquire.run("canary", fetch=station_coordinate_conflict_fetch)
                second = acquire.run("canary", fetch=station_coordinate_conflict_fetch)
                self.assertEqual(first["daily_snapshot_files"][0]["sha256"], second["daily_snapshot_files"][0]["sha256"])
                self.assertEqual(second["canary_quality"]["station_hours_with_coordinate_variants"], 1)

    def test_metadata_contract_fingerprint_is_semantic(self):
        m1 = metadata()
        m2 = {**m1, "viewCount": 1000000}
        fields = {c["fieldName"]: c["dataTypeName"] for c in m1["columns"]}
        self.assertEqual(acquire.stable_metadata_fingerprint(m1, fields), acquire.stable_metadata_fingerprint(m2, fields))
        self.assertNotEqual(acquire.stable_metadata_fingerprint(m1, fields), acquire.stable_metadata_fingerprint({**m2, "rowsUpdatedAt": 500}, fields))


if __name__ == "__main__":
    unittest.main()
