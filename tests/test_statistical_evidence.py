import unittest
from datetime import timedelta

import pandas as pd

from commuter_rush.statistical_evidence import (
    borough_peak_evidence, daytype_uncertainty, peak_day_evidence, percentile_interval,
)


def synthetic_month():
    rows = []
    for date in pd.date_range('2024-10-01', '2024-10-31', freq='D'):
        weekday = date.weekday() < 5
        factor = 1 + (date.day % 5) / 10
        for id_, borough in [('1', 'Manhattan'), ('2', 'Brooklyn'), ('3', 'Queens'), ('4', 'Bronx')]:
            for hour in range(24):
                entries = 10
                if weekday and hour in (7, 8, 9):
                    entries = 30 if borough == 'Manhattan' else 50
                if weekday and hour in (16, 17, 18):
                    entries = 80 if borough == 'Manhattan' else 25
                entries *= factor if weekday else .7
                rows.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'day_type': 'Weekday' if weekday else 'Weekend',
                    'hour': hour,
                    'estimated_entries': entries,
                    'station_complex_id': id_,
                    'station_complex': f'Complex {id_}',
                    'borough': borough,
                    'timestamp': date + timedelta(hours=hour),
                })
    return pd.DataFrame(rows)


class StatisticalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = synthetic_month()

    def test_bootstrap_is_deterministic(self):
        a = percentile_interval([2, 3, 4, 5, 6], 1000)
        self.assertEqual(a, percentile_interval([2, 3, 4, 5, 6], 1000))
        self.assertLess(a[0], a[1])

    def test_daytype_sample_uses_days_not_station_hours(self):
        result, daily = daytype_uncertainty(self.frame, 1000)
        self.assertEqual(len(daily), 31)
        self.assertEqual(result.iloc[0]['weekday_days'], 23)
        self.assertEqual(result.iloc[0]['weekend_days'], 8)
        self.assertGreater(result.iloc[0]['weekday_to_weekend_mean_ratio'], 1)

    def test_weekday_peak_days_are_paired(self):
        paired, summary = peak_day_evidence(self.frame, 1000)
        self.assertEqual(len(paired), 23)
        self.assertAlmostEqual(summary['aggregate_morning_share_pct'],
                               100 * paired['morning'].sum() / paired['all_entries'].sum())
        self.assertLess(summary['mean_daily_evening_minus_morning_pp'], 0)

    def test_borough_peak_contrast_is_day_paired(self):
        boroughs, paired, contrast = borough_peak_evidence(self.frame, 1000)
        self.assertEqual(len(boroughs), 4)
        self.assertEqual(len(paired), 92)
        self.assertGreater(boroughs.set_index('borough').loc['Manhattan',
            'mean_daily_evening_minus_morning_pp'], 0)
        self.assertLess(boroughs.set_index('borough').loc['Queens',
            'mean_daily_evening_minus_morning_pp'], 0)
        self.assertGreater(contrast['mean_manhattan_minus_other_boroughs_pp'], 0)

    def test_missing_borough_day_is_rejected(self):
        damaged = self.frame.loc[
            ~((self.frame['date'] == '2024-10-02') & (self.frame['borough'] == 'Bronx'))
        ]
        from commuter_rush.temporal_analysis import AnalysisError
        with self.assertRaises(AnalysisError):
            borough_peak_evidence(damaged, 1000)


if __name__ == '__main__':
    unittest.main()
