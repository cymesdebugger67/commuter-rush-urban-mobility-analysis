from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json
import math
import unittest

import pandas as pd

from commuter_rush.monthly_quality import ANALYTICAL_FIELDS
from commuter_rush.temporal_analysis import (
    AnalysisError, build_tables, file_sha256, gini_coefficient,
    output_report, result_summary, validated_frame, verify_source, write_tables,
)


class TemporalAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.csv_path = self.root / "station_hours.csv"
        self.manifest_path = self.root / "manifest.json"
        self.rows = []
        for ts in pd.date_range("2024-10-01", "2024-10-31 23:00:00", freq="h"):
            for station, name, borough, lat, lon, entries in (
                ("A", "Station A", "Manhattan", "40.7378", "-73.9967", 100 + ts.hour),
                ("B", "Station B", "Queens", "40.7500", "-73.8000", 40 + ts.hour),
            ):
                self.rows.append({
                    "transit_timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    "station_complex_id": station,
                    "station_complex": name,
                    "borough": borough,
                    "latitude": lat,
                    "longitude": lon,
                    "estimated_entries": str(entries),
                    "included_transfers": "2",
                    "fare_rows": "3",
                })
        self.refresh()

    def refresh(self):
        with self.csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=ANALYTICAL_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)
        dates = {row["transit_timestamp"][:10] for row in self.rows}
        hours = {row["transit_timestamp"] for row in self.rows}
        stations = {row["station_complex_id"] for row in self.rows}
        quality = {
            "station_hour_rows": len(self.rows),
            "estimated_entries": str(sum(float(row["estimated_entries"]) for row in self.rows)),
            "included_transfers_subset": str(sum(float(row["included_transfers"]) for row in self.rows)),
            "source_fare_rows_reconciled": sum(int(row["fare_rows"]) for row in self.rows),
            "unique_station_complexes": len(stations),
            "observed_clock_hours": len(hours),
            "all_daily_source_controls_reconciled": True,
            "station_hour_keys_unique": True,
            "source_metadata_conflicts_preserved": True,
            "missing_station_hours_not_assumed_zero": True,
            "station_hours_with_coordinate_variants": 0,
            "station_ids_with_multiple_metadata_variants": 0,
        }
        manifest = {
            "dataset_id": "wujg-7c2s",
            "status": "month_acquisition_passed",
            "days_completed": len(dates),
            "month_quality": quality,
            "processed_csv": {"sha256": file_sha256(self.csv_path), "bytes": self.csv_path.stat().st_size},
            "daily_snapshot_files": [{} for _ in dates],
            "metadata_policy": "Fixture representative coordinates",
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def load(self):
        m = verify_source(self.csv_path, self.manifest_path)
        f = validated_frame(self.csv_path, m)
        return f, m

    def test_complete_month_and_source_reconciliation(self):
        frame, m = self.load()
        self.assertEqual(len(frame), 1488)
        self.assertEqual(frame["timestamp"].nunique(), 744)
        self.assertEqual(frame["station_complex_id"].nunique(), 2)
        self.assertEqual(m["month_quality"]["source_fare_rows_reconciled"], 4464)

    def test_csv_sha_mismatch_stops_before_reading(self):
        self.csv_path.write_bytes(self.csv_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(AnalysisError, "fingerprint"):
            verify_source(self.csv_path, self.manifest_path)

    def test_duplicate_station_hour_is_rejected(self):
        self.rows[1]["station_complex_id"] = "A"
        self.refresh()
        with self.assertRaisesRegex(AnalysisError, "Repeated"):
            self.load()

    def test_one_missing_system_hour_rejected(self):
        self.rows = [row for row in self.rows if row["transit_timestamp"] != "2024-10-07T12:00:00"]
        self.refresh()
        with self.assertRaisesRegex(AnalysisError, "744|missing|monthly quality"):
            self.load()

    def test_transfer_overcount_rejected(self):
        self.rows[0]["included_transfers"] = "9999"
        self.refresh()
        with self.assertRaisesRegex(AnalysisError, "Transfers exceed"):
            self.load()

    def test_no_station_hour_zero_imputation(self):
        self.rows = [row for row in self.rows if not (
            row["station_complex_id"] == "B" and row["transit_timestamp"] == "2024-10-07T07:00:00"
        )]
        self.refresh()
        frame, manifest = self.load()
        tables = build_tables(frame)
        self.assertEqual(len(frame), 1487)
        self.assertEqual(int(tables["daily_entry_summary"]["observed_station_hours"].min()), 47)
        self.assertEqual(len(tables["daily_entry_summary"]), 31)
        self.assertGreater(tables["station_weekday_peak_profiles"].loc[
            lambda d: d["station_complex_id"].eq("B"), "morning_coverage_pct"
        ].iloc[0], 90)

    def test_day_type_exposure_normalization(self):
        frame, manifest = self.load()
        tables = build_tables(frame)
        counts = tables["daytype_entry_summary"].set_index("day_type")["days"].to_dict()
        self.assertEqual(counts, {"Weekday": 23, "Weekend": 8})
        hourly = tables["hourly_daytype_profiles"]
        self.assertEqual(len(hourly), 48)
        self.assertTrue(hourly["mean_entries_per_day"].gt(0).all())
        day_hour = frame.loc[frame["hour"].eq(7)]
        self.assertTrue(math.isclose(
            hourly.loc[(hourly["day_type"] == "Weekday") & (hourly["hour"] == 7), "mean_entries_per_day"].iloc[0],
            day_hour.loc[day_hour["day_type"].eq("Weekday"), "estimated_entries"].sum() / 23,
        ))

    def test_all_tables_and_peak_exposures(self):
        frame, manifest = self.load()
        tables = build_tables(frame)
        self.assertEqual(len(tables), 10)
        summary = result_summary(frame, tables, manifest)
        weekday = frame[frame["weekday_number"] < 5]
        expected = weekday.loc[weekday["hour"].isin([7, 8, 9]), "estimated_entries"].sum()
        self.assertEqual(summary["weekday_morning_entries"], expected)
        self.assertTrue(0 < summary["weekday_morning_share_pct"] < 100)
        self.assertEqual(summary["peak_ranking_eligible_station_complexes"], 2)
        self.assertAlmostEqual(summary["top_10_station_share_pct"], 100)
        report = output_report(summary, tables)
        self.assertIn("Cyril James Lunzaga", report)
        self.assertIn("not unique commuter trips", report)

    def test_peak_ranking_requires_90_percent_coverage(self):
        self.rows = [row for row in self.rows if not (
            row["station_complex_id"] == "B"
            and datetime.fromisoformat(row["transit_timestamp"]).weekday() < 5
            and datetime.fromisoformat(row["transit_timestamp"]).hour in (7, 8, 9)
        )]
        self.refresh()
        frame, manifest = self.load()
        tables = build_tables(frame)
        summary = result_summary(frame, tables, manifest)
        self.assertEqual(summary["peak_ranking_excluded_station_complexes"], 1)
        self.assertEqual(tables["top_weekday_morning_stations"]["station_complex_id"].tolist(), ["A"])

    def test_gini_definition(self):
        self.assertAlmostEqual(gini_coefficient([1, 1, 1]), 0.0)
        self.assertAlmostEqual(gini_coefficient([0, 0, 10]), 2 / 3)
        with self.assertRaises(AnalysisError):
            gini_coefficient([0, 0])

    def test_deterministic_table_artifact_names(self):
        frame, manifest = self.load()
        tables = build_tables(frame)
        out = self.root / "tables"
        index = write_tables(tables, out)
        self.assertEqual(len(index), 10)
        self.assertEqual(index["daily_entry_summary"]["rows"], 31)
        self.assertEqual(file_sha256(out / "daily_entry_summary.csv"), index["daily_entry_summary"]["sha256"])


if __name__ == "__main__":
    unittest.main()
