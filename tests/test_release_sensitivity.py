from pathlib import Path
import csv
import tempfile
import unittest

from commuter_rush.release_sensitivity import EXCLUDED_DATE, calculate, write_outputs
from commuter_rush.temporal_analysis import AnalysisError


class ReleaseSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'tests' / 'fixtures'
        cls.daily = []
        cls.pairs = []
        from datetime import date, timedelta
        start = date(2024, 10, 1)
        for offset in range(31):
            day = start + timedelta(days=offset)
            weekday = day.weekday() < 5
            value = 150 if weekday else 100
            if day.isoformat() == EXCLUDED_DATE:
                value = 100
            cls.daily.append({'date': day.isoformat(), 'day_type': 'Weekday' if weekday else 'Weekend', 'estimated_entries': str(value)})
            if weekday:
                morn, eve = (20, 35) if day.isoformat() == EXCLUDED_DATE else (30, 40)
                cls.pairs.append({'date': day.isoformat(), 'morning': str(morn), 'evening': str(eve), 'all_entries': str(value), 'evening_minus_morning_pp': str(100 * (eve-morn)/value)})

    def test_baseline_and_exclusion_use_distinct_day_counts(self):
        baseline = calculate(self.daily, self.pairs, reps=1000)
        exclusion = calculate(self.daily, self.pairs, EXCLUDED_DATE, reps=1000)
        self.assertEqual((baseline['weekday_days'], baseline['weekend_days']), (23, 8))
        self.assertEqual((exclusion['weekday_days'], exclusion['weekend_days']), (22, 8))
        self.assertGreater(exclusion['weekday_weekend_ratio'], baseline['weekday_weekend_ratio'])
        self.assertEqual(exclusion['evening_greater_weekdays'], 22)

    def test_bootstrap_is_reproducible(self):
        first = calculate(self.daily, self.pairs, EXCLUDED_DATE, reps=1000)
        second = calculate(self.daily, self.pairs, EXCLUDED_DATE, reps=1000)
        self.assertEqual(first, second)

    def test_duplicate_day_rejected(self):
        with self.assertRaises(AnalysisError):
            calculate(self.daily + self.daily[:1], self.pairs, reps=1000)

    def test_omitted_weekday_pair_rejected(self):
        with self.assertRaises(AnalysisError):
            calculate(self.daily, self.pairs[:-1], reps=1000)

    def test_incorrect_peak_total_rejected(self):
        damaged = [dict(item) for item in self.pairs]
        damaged[0]['all_entries'] = '999'
        with self.assertRaises(AnalysisError):
            calculate(self.daily, damaged, reps=1000)

    def test_nonweekday_exclusion_rejected(self):
        with self.assertRaises(AnalysisError):
            calculate(self.daily, self.pairs, '2024-10-06', reps=1000)

    def test_sensitivity_direction_not_hardcoded(self):
        baseline = calculate(self.daily, self.pairs, reps=1000)
        altered = [dict(item) for item in self.pairs]
        for row in altered:
            if row['date'] == EXCLUDED_DATE:
                row['evening'] = '20'
                row['morning'] = '35'
                row['evening_minus_morning_pp'] = '-15'
        revised = calculate(self.daily, altered, reps=1000)
        self.assertLess(revised['mean_evening_minus_morning_pp'], baseline['mean_evening_minus_morning_pp'])
