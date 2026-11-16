import unittest

from commuter_rush.station_behaviors import (
    classify_peak_balance, station_typologies, window_balance,
)
from test_statistical_evidence import synthetic_month
from commuter_rush.temporal_analysis import AnalysisError


class StationBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = synthetic_month()

    def test_threshold_is_symmetric(self):
        self.assertEqual(classify_peak_balance(-.2), 'morning-oriented')
        self.assertEqual(classify_peak_balance(.2), 'evening-oriented')
        self.assertEqual(classify_peak_balance(0), 'balanced')

    def test_station_profiles_retain_all_stations(self):
        stations, boroughs, summary = station_typologies(self.frame)
        self.assertEqual(len(stations), 4)
        self.assertEqual(summary['primary_eligible_stations'], 4)
        self.assertEqual(summary['eligible_in_both_windows'], 4)
        self.assertEqual(summary['stable_orientation_share_pct'], 100)
        self.assertEqual(sum(boroughs['station_complexes']), 4)

    def test_manhattan_and_outer_pattern(self):
        stations, _, _ = station_typologies(self.frame)
        lookup = stations.set_index('borough')['orientation'].to_dict()
        self.assertEqual(lookup['Manhattan'], 'evening-oriented')
        self.assertEqual(lookup['Queens'], 'morning-oriented')

    def test_missing_hours_are_not_zero_imputed(self):
        removed = self.frame.loc[
            ~((self.frame['station_complex_id'] == '1') & (self.frame['hour'] == 7)
              & (self.frame['day_type'] == 'Weekday'))
        ]
        stations, _, _ = station_typologies(removed)
        affected = stations.set_index('station_complex_id').loc['1']
        self.assertFalse(bool(affected['eligible']))
        self.assertEqual(affected['orientation'], 'not_eligible')

    def test_invalid_windows_rejected(self):
        with self.assertRaises(AnalysisError):
            window_balance(self.frame, (7, 8), (8, 9), 23)


if __name__ == '__main__':
    unittest.main()
