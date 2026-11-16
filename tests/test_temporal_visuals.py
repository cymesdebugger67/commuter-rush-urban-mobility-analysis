from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from commuter_rush.temporal_analysis import AnalysisError, build_tables, file_sha256, write_tables
from commuter_rush import temporal_visuals
import test_temporal_analysis as fixtures


class TemporalVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixtures.TemporalAnalysisTests()
        cls.fixture.setUp()
        cls.frame, cls.manifest = cls.fixture.load()
        cls.tables = build_tables(cls.frame)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.doCleanups()

    def test_six_visualizations_write_nonempty_pngs(self):
        with TemporaryDirectory() as temp:
            dest = Path(temp)
            functions = (
                ("daily", temporal_visuals.daily_entries_chart, "daily_entry_summary"),
                ("hourly", temporal_visuals.hourly_daytype_chart, "hourly_daytype_profiles"),
                ("heat", temporal_visuals.weekday_hour_heatmap, "weekday_hourly_profiles"),
                ("borough", temporal_visuals.borough_peak_chart, "borough_weekday_peak_shares"),
                ("stations", temporal_visuals.top_station_chart, "station_entry_concentration"),
                ("concentration", temporal_visuals.station_concentration_chart, "station_entry_concentration"),
            )
            for label, renderer, table in functions:
                with self.subTest(label=label):
                    path = renderer(self.tables[table], dest)
                    self.assertTrue(path.is_file())
                    self.assertGreater(path.stat().st_size, 2000)
                    self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_fingerprint_guard_rejects_modified_tables(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            tables = root / "tables"
            records = write_tables(self.tables, tables)
            index = root / "descriptive_artifacts.json"
            for key, value in records.items():
                value["path"] = (tables / f"{key}.csv").as_posix()
            index.write_text(json.dumps({"tables": records}), encoding="utf-8")
            with patch.object(temporal_visuals, "TABLE_DIRECTORY", tables):
                temporal_visuals.verified_tables(index)
                path = tables / "daily_entry_summary.csv"
                path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaisesRegex(AnalysisError, "fingerprint"):
                    temporal_visuals.verified_tables(index)


if __name__ == "__main__":
    unittest.main()
