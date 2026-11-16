import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from commuter_rush.monthly_quality import (
    day_quality, dates_in_study, normalize_grouped_row, summarize_month, write_month_csv_atomic,
    collapse_station_hour_variants,
)
from commuter_rush.source_contract import SourceContractError


def one_hour(day, hour=8, **changes):
    row = {
        "transit_timestamp": f"{day}T{hour:02d}:00:00.000",
        "station_complex_id": "101", "station_complex": "Synthetic Station", "borough": "Manhattan",
        "latitude": "40.751", "longitude": "-73.99",
        "estimated_entries": "21.5", "included_transfers": "3.5", "fare_rows": "3",
    }
    row.update(changes)
    return normalize_grouped_row(row, date.fromisoformat(day))


def snapshot(day):
    rows = [one_hour(day, hour) for hour in range(24)]
    control = {"fare_rows": "72", "estimated_entries": "516", "included_transfers": "84"}
    return {"date": day, "rows": rows, "control": control}


class MonthlyQualityTests(unittest.TestCase):
    def test_study_month_has_31_days(self):
        days = list(dates_in_study())
        self.assertEqual(len(days), 31)
        self.assertEqual(days[0].isoformat(), "2024-10-01")
        self.assertEqual(days[-1].isoformat(), "2024-10-31")

    def test_normalizes_one_station_hour(self):
        row = one_hour("2024-10-09")
        self.assertEqual(row["transit_timestamp"], "2024-10-09T08:00:00")
        self.assertEqual(row["fare_rows"], 3)
        self.assertEqual(row["estimated_entries"], "21.5")

    def test_invalid_grouping_values_stop(self):
        cases = [
            {"station_complex_id": ""}, {"estimated_entries": "-1"},
            {"estimated_entries": "NaN"}, {"included_transfers": "30"},
            {"fare_rows": "1.5"}, {"longitude": None},
            {"latitude": "4.5"}, {"transit_timestamp": "2024-11-01T08:00:00"},
        ]
        for modifications in cases:
            with self.subTest(modifications=modifications), self.assertRaises(SourceContractError):
                one_hour("2024-10-09", **modifications)

    def test_day_source_controls_reconcile(self):
        s = snapshot("2024-10-09")
        quality = day_quality(s["rows"], date(2024, 10, 9), s["control"])
        self.assertEqual(quality["observed_hour_count"], 24)
        self.assertEqual(quality["source_fare_rows"], 72)
        self.assertTrue(quality["independent_source_totals_reconciled"])

    def test_day_source_mismatch_stops(self):
        s = snapshot("2024-10-09")
        s["control"]["estimated_entries"] = "517"
        with self.assertRaisesRegex(SourceContractError, "reconcile"):
            day_quality(s["rows"], date(2024, 10, 9), s["control"])

    def test_repeated_station_hour_rejected(self):
        s = snapshot("2024-10-09")
        s["rows"].append(s["rows"][0])
        with self.assertRaisesRegex(SourceContractError, "Repeated station-hour"):
            day_quality(s["rows"], date(2024, 10, 9), s["control"])

    def test_missing_station_hours_not_imputed(self):
        s = snapshot("2024-10-09")
        s["rows"].pop()
        s["control"] = {"fare_rows": "69", "estimated_entries": "494.5", "included_transfers": "80.5"}
        q = day_quality(s["rows"], date(2024, 10, 9), s["control"])
        self.assertEqual(q["missing_clock_hours"], [23])

    def test_full_month_coverage_and_reconciliation(self):
        snapshots = [snapshot(day.isoformat()) for day in dates_in_study()]
        report = summarize_month(snapshots)
        self.assertEqual(report["observed_clock_hours"], 744)
        self.assertEqual(report["station_hour_rows"], 744)
        self.assertEqual(report["source_fare_rows_reconciled"], 2232)
        self.assertEqual(Decimal(report["estimated_entries"]), Decimal("15996"))
        self.assertTrue(report["missing_station_hours_not_assumed_zero"])
        with tempfile.TemporaryDirectory() as folder:
            output = write_month_csv_atomic(Path(folder) / "month.csv", snapshots)
            self.assertEqual(len(output["sha256"]), 64)
            self.assertTrue((Path(folder) / "month.csv").exists())

    def test_station_601_coordinate_variants_reconcile_without_dropping_entries(self):
        first = one_hour(
            "2024-10-09", hour=0, station_complex_id="601",
            station_complex="14 St (F,M,1,2,3)/6 Av (L)",
            latitude="40.737827", longitude="-73.99679",
            fare_rows="1", estimated_entries="2", included_transfers="0",
        )
        second = one_hour(
            "2024-10-09", hour=0, station_complex_id="601",
            station_complex="14 St (F,M,1,2,3)/6 Av (L)",
            latitude="40.738228", longitude="-73.99621",
            fare_rows="9", estimated_entries="284", included_transfers="4",
        )
        collapsed, conflicts = collapse_station_hour_variants([first, second])
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(collapsed[0]["fare_rows"], 10)
        self.assertEqual(collapsed[0]["estimated_entries"], "286")
        self.assertEqual(collapsed[0]["included_transfers"], "4")
        self.assertEqual(collapsed[0]["latitude"], "40.738228")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["distinct_coordinate_pairs"], 2)
        quality = day_quality(
            collapsed, date(2024, 10, 9),
            {"fare_rows": 10, "estimated_entries": "286", "included_transfers": "4"},
            conflicts, 2,
        )
        self.assertEqual(quality["station_hours_with_coordinate_variants"], 1)
        self.assertEqual(quality["source_metadata_rows_collapsed"], 1)
        self.assertTrue(quality["source_metadata_conflicts_preserved"])

    def test_identical_metadata_duplicate_is_rejected(self):
        first = one_hour("2024-10-09", fare_rows="2")
        second = one_hour("2024-10-09", fare_rows="3")
        with self.assertRaisesRegex(SourceContractError, "Repeated identical source metadata group"):
            collapse_station_hour_variants([first, second])

    def test_same_station_hour_borough_conflict_stops(self):
        first = one_hour("2024-10-09", borough="Manhattan")
        second = one_hour("2024-10-09", borough="Brooklyn", latitude="40.752")
        with self.assertRaisesRegex(SourceContractError, "conflicting borough"):
            collapse_station_hour_variants([first, second])

    def test_changed_audit_is_rejected(self):
        first = one_hour("2024-10-09", latitude="40.751")
        second = one_hour("2024-10-09", latitude="40.752")
        collapsed, conflicts = collapse_station_hour_variants([first, second])
        conflicts[0]["source_variant_rows"][0]["estimated_entries"] = "1000"
        with self.assertRaisesRegex(SourceContractError, "Cached metadata conflict audit"):
            day_quality(collapsed, date(2024, 10, 9), {
                "fare_rows": 6, "estimated_entries": "43", "included_transfers": "7",
            }, conflicts, 2)

    def test_source_group_row_count_mismatch_rejected(self):
        first = one_hour("2024-10-09", latitude="40.751")
        second = one_hour("2024-10-09", latitude="40.752")
        collapsed, conflicts = collapse_station_hour_variants([first, second])
        with self.assertRaisesRegex(SourceContractError, "Source grouped row count"):
            day_quality(collapsed, date(2024, 10, 9), {
                "fare_rows": 6, "estimated_entries": "43", "included_transfers": "7",
            }, conflicts, 3)

    def test_incomplete_month_rejected(self):
        snapshots = [snapshot(day.isoformat()) for day in list(dates_in_study())[:-1]]
        with self.assertRaisesRegex(SourceContractError, "Month incomplete"):
            summarize_month(snapshots)


if __name__ == "__main__":
    unittest.main()
