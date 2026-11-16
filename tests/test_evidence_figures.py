import tempfile
import unittest
from pathlib import Path

import pandas as pd

from commuter_rush.evidence_figures import borough_interval_figure, orientation_figure, daytype_figure


class EvidenceFigureTests(unittest.TestCase):
    def test_three_original_statistical_figures_render(self):
        boroughs = pd.DataFrame([
            {'borough': borough, 'mean_daily_evening_minus_morning_pp': value,
             'difference_ci_low': value - 2, 'difference_ci_high': value + 2}
            for borough, value in [('Bronx', -11), ('Brooklyn', -8), ('Queens', -13), ('Manhattan', 14)]
        ])
        orientation = pd.DataFrame([
            {'borough': borough, 'orientation': orientation,
             'share_of_eligible_borough_stations_pct': 100 / 3}
            for borough in ('Bronx', 'Brooklyn', 'Queens', 'Manhattan')
            for orientation in ('morning-oriented', 'balanced', 'evening-oriented')
        ])
        daily = pd.DataFrame([
            {'day_type': 'Weekday' if date.weekday() < 5 else 'Weekend',
             'estimated_entries': 4e6 if date.weekday() < 5 else 2e6}
            for date in pd.date_range('2024-10-01', '2024-10-31', freq='D')
        ])
        with tempfile.TemporaryDirectory() as temporary:
            dest = Path(temporary)
            figures = [
                borough_interval_figure(boroughs, dest),
                orientation_figure(orientation, dest),
                daytype_figure(daily, dest),
            ]
            self.assertEqual(len(figures), 3)
            for figure in figures:
                self.assertTrue(figure.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertGreater(figure.stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
