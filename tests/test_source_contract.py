import tempfile
import unittest
from pathlib import Path

from commuter_rush.source_contract import (
    DATASET_ID, REQUIRED_COLUMNS, SourceContractError, metadata_contract,
    nonnegative_decimal, parse_station_hour, reconcile_station_hour,
    validate_records, write_json_atomic,
)
from commuter_rush.source_probe import bound_where, query_url, station_literal


def sample_row(**changes):
    row = {
        "transit_timestamp": "2024-10-09T08:00:00.000",
        "transit_mode": "subway",
        "station_complex_id": "100",
        "station_complex": "Test Complex",
        "borough": "Manhattan",
        "payment_method": "metrocard",
        "fare_class_category": "Full Fare",
        "ridership": "10",
        "transfers": "2",
        "latitude": "40.75",
        "longitude": "-73.99",
    }
    row.update(changes)
    return row


class SourceContractTests(unittest.TestCase):
    def test_metadata_requires_authorized_source_and_columns(self):
        metadata = {
            "id": DATASET_ID,
            "columns": [{"fieldName": name, "dataTypeName": "text"} for name in REQUIRED_COLUMNS],
        }
        self.assertEqual(set(metadata_contract(metadata)), REQUIRED_COLUMNS)
        with self.assertRaises(SourceContractError):
            metadata_contract({**metadata, "id": "unrelated"})
        with self.assertRaises(SourceContractError):
            metadata_contract({**metadata, "columns": []})

    def test_hour_alignment_and_source_local_time(self):
        self.assertEqual(parse_station_hour("2024-10-09T08:00:00").hour, 8)
        for timestamp in ("2024-10-09T08:30:00", "2024-10-09T08:00:00Z", "not-a-date"):
            with self.subTest(timestamp=timestamp), self.assertRaises(SourceContractError):
                parse_station_hour(timestamp)

    def test_valid_sample_has_stations_and_boroughs(self):
        quality = validate_records([
            sample_row(),
            sample_row(station_complex_id="101", fare_class_category="Students", ridership="5", transfers="0"),
        ])
        self.assertEqual(quality["sample_rows"], 2)
        self.assertEqual(quality["sample_distinct_stations"], 2)
        self.assertEqual(quality["repeated_station_hour_payment_fare_keys"], 0)

    def test_repeated_fare_key_is_flagged_not_silently_removed(self):
        result = validate_records([sample_row(), sample_row(ridership="5")])
        self.assertEqual(result["repeated_station_hour_payment_fare_keys"], 1)

    def test_missing_coordinates_are_reported(self):
        self.assertEqual(validate_records([sample_row(latitude=None)])["null_coordinate_rows"], 1)

    def test_invalid_values_are_rejected(self):
        cases = [
            {"transit_mode": "tram"},
            {"transit_timestamp": "2024-11-01T08:00:00"},
            {"station_complex_id": ""},
            {"ridership": "-1"},
            {"ridership": "NaN"},
            {"transfers": "11"},
            {"latitude": "13.3"},
            {"fare_class_category": ""},
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(SourceContractError):
                validate_records([sample_row(**changes)])

    def test_reconciliation_matches_client_and_server(self):
        rows = [
            sample_row(),
            sample_row(payment_method="omny", fare_class_category="OMNY Full", ridership="25", transfers="3"),
        ]
        aggregate = [{"station_complex_id": "100", "fare_rows": "2", "estimated_entries": "35", "included_transfers": "5"}]
        result = reconcile_station_hour(rows, aggregate, "100")
        self.assertEqual(result["estimated_station_hour_entries"], "35")
        self.assertTrue(result["source_to_client_reconciled"])

    def test_reconciliation_rejects_inflated_server_total(self):
        aggregate = [{"station_complex_id": "100", "fare_rows": "1", "estimated_entries": "20", "included_transfers": "2"}]
        with self.assertRaises(SourceContractError):
            reconcile_station_hour([sample_row()], aggregate, "100")

    def test_reconciliation_rejects_truncated_fare_extract(self):
        rows = [sample_row() for _ in range(1000)]
        with self.assertRaises(SourceContractError):
            reconcile_station_hour(rows, [], "100")

    def test_api_queries_are_bounded_and_escape_identifiers(self):
        self.assertIn("2024-10-09T08:00:00", bound_where())
        self.assertIn("transit_mode = 'subway'", bound_where())
        self.assertEqual(station_literal("A'B"), "'A''B'")
        self.assertIn("%24limit=1", query_url({"$limit": 1}))

    def test_atomic_manifest_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "nested" / "manifest.json"
            write_json_atomic(destination, {"count": 2})
            self.assertIn('"count": 2', destination.read_text(encoding="utf-8"))
            self.assertFalse(destination.with_suffix(".json.partial").exists())

    def test_rejects_nonfinite_decimal(self):
        with self.assertRaises(SourceContractError):
            nonnegative_decimal(float("inf"), "ridership")


if __name__ == "__main__":
    unittest.main()
