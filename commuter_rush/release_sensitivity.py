from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
import math
import os
from datetime import date, datetime
from pathlib import Path

import numpy as np

from commuter_rush.temporal_analysis import AnalysisError, SOURCE_CSV, SOURCE_MANIFEST, file_sha256, verify_source, write_json_atomic

TABLES = Path('portfolio/tables')
REPORTS = Path('portfolio/reports')
OUTPUT = Path('outputs/release_readiness')
EXCLUDED_DATE = '2024-10-14'
SOURCE_SHA256 = '0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb'
REPS = 10000
SEED = 202410


def _read_table(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def _bootstrap(weekdays, weekends, differences, reps=REPS, seed=SEED):
    rng = np.random.default_rng(seed)
    a = np.asarray(weekdays, dtype=float)
    b = np.asarray(weekends, dtype=float)
    c = np.asarray(differences, dtype=float)
    if len(a) < 2 or len(b) < 2 or len(c) != len(a) or (b <= 0).any():
        raise AnalysisError('Insufficient independent calendar-day observations')
    if not all(np.isfinite(arr).all() for arr in (a, b, c)):
        raise AnalysisError('Invalid day-level numerical input')
    draws_a = a[rng.integers(0, len(a), size=(reps, len(a)))].mean(axis=1)
    draws_b = b[rng.integers(0, len(b), size=(reps, len(b)))].mean(axis=1)
    draws_c = c[rng.integers(0, len(c), size=(reps, len(c)))].mean(axis=1)
    ratio = draws_a / draws_b
    return [float(np.quantile(ratio, 0.025)), float(np.quantile(ratio, 0.975))], [float(np.quantile(draws_c, 0.025)), float(np.quantile(draws_c, 0.975))]


def calculate(daily_rows, paired_rows, exclude_date=None, reps=REPS):
    daily = {}
    for row in daily_rows:
        day = row['date']
        if day in daily:
            raise AnalysisError('Duplicate calendar date in daily evidence')
        parsed = date.fromisoformat(day)
        kind = 'Weekday' if parsed.weekday() < 5 else 'Weekend'
        if kind != row['day_type'] or not (date(2024, 10, 1) <= parsed < date(2024, 11, 1)):
            raise AnalysisError('Calendar classification or study period mismatch')
        count = float(row['estimated_entries'])
        if not math.isfinite(count) or count <= 0:
            raise AnalysisError('Nonpositive or invalid daily entries')
        daily[day] = (kind, count)
    if len(daily) != 31:
        raise AnalysisError('October must contain 31 separately observed dates')
    pairs = {}
    for row in paired_rows:
        day = row['date']
        if day in pairs or day not in daily or daily[day][0] != 'Weekday':
            raise AnalysisError('Duplicate or invalid paired weekday')
        morning = float(row['morning'])
        evening = float(row['evening'])
        total = float(row['all_entries'])
        given_diff = float(row['evening_minus_morning_pp'])
        computed = 100 * (evening - morning) / total
        if (not all(math.isfinite(x) for x in (morning, evening, total, given_diff))
                or min(morning, evening) < 0 or max(morning, evening) > total
                or not math.isclose(total, daily[day][1], abs_tol=.001, rel_tol=0)
                or not math.isclose(given_diff, computed, abs_tol=1e-8, rel_tol=0)):
            raise AnalysisError('Paired weekday values do not reconcile')
        pairs[day] = computed
    if len(pairs) != 23 or set(pairs) != {d for d, (kind, _) in daily.items() if kind == 'Weekday'}:
        raise AnalysisError('Incomplete paired weekday inventory')
    if exclude_date is not None and (exclude_date not in pairs):
        raise AnalysisError('Sensitivity exclusion is not an observed weekday')
    retained = {d: row for d, row in daily.items() if d != exclude_date}
    weekdays = [value for day, (kind, value) in sorted(retained.items()) if kind == 'Weekday']
    weekends = [value for day, (kind, value) in sorted(retained.items()) if kind == 'Weekend']
    differences = [pairs[day] for day, (kind, _) in sorted(retained.items()) if kind == 'Weekday']
    if len(weekdays) != (22 if exclude_date else 23) or len(weekends) != 8:
        raise AnalysisError('Unexpected day-type samples after exclusion')
    mean_weekday = float(np.mean(weekdays))
    mean_weekend = float(np.mean(weekends))
    ratio_ci, diff_ci = _bootstrap(weekdays, weekends, differences, reps=reps)
    return {
        'scenario': 'exclude_2024_10_14' if exclude_date else 'all_october_days',
        'excluded_date': exclude_date or '',
        'weekday_days': len(weekdays),
        'weekend_days': len(weekends),
        'mean_weekday_entries': mean_weekday,
        'mean_weekend_entries': mean_weekend,
        'weekday_weekend_ratio': mean_weekday / mean_weekend,
        'weekday_weekend_ratio_ci_low': ratio_ci[0],
        'weekday_weekend_ratio_ci_high': ratio_ci[1],
        'mean_evening_minus_morning_pp': float(np.mean(differences)),
        'mean_difference_ci_low': diff_ci[0],
        'mean_difference_ci_high': diff_ci[1],
        'evening_greater_weekdays': sum(delta > 0 for delta in differences),
    }


def verify_inputs():
    source = verify_source(SOURCE_CSV, SOURCE_MANIFEST)
    if file_sha256(SOURCE_CSV) != SOURCE_SHA256:
        raise AnalysisError('Unapproved processed October source fingerprint')
    temporal = json.loads(Path('outputs/temporal_analysis/descriptive_artifacts.json').read_text(encoding='utf-8'))
    statistical = json.loads(Path('outputs/statistical_evidence/statistical_summary.json').read_text(encoding='utf-8'))
    files = {
        'calendar_day_entries': TABLES / 'calendar_day_entries.csv',
        'weekday_peak_day_pairs': TABLES / 'weekday_peak_day_pairs.csv',
    }
    for name, path in files.items():
        item = statistical['table_artifacts'][name]
        if not path.is_file() or file_sha256(path) != item['sha256']:
            raise AnalysisError(f'Reviewed input table was changed: {path}')
    if statistical.get('source_csv_sha256') != SOURCE_SHA256:
        raise AnalysisError('Statistical source fingerprint mismatch')
    try:
        source_entries = Decimal(str(source['month_quality']['estimated_entries']))
    except (InvalidOperation, ValueError) as exc:
        raise AnalysisError('Invalid monthly estimated entry total') from exc
    if not source_entries.is_finite() or source_entries != Decimal('114680137'):
        raise AnalysisError('Monthly MTA entries differ from reviewed value')
    return files, statistical, source


def write_outputs(daily_rows, paired_rows, statistical, table_dir=TABLES, report_dir=REPORTS, output_dir=OUTPUT):
    original = calculate(daily_rows, paired_rows)
    excluded = calculate(daily_rows, paired_rows, EXCLUDED_DATE)
    day_entries = {r['date']: float(r['estimated_entries']) for r in daily_rows}
    if not math.isclose(sum(day_entries.values()), 114680137, abs_tol=.01, rel_tol=0):
        raise AnalysisError('Daily input does not sum to the verified monthly total')
    if not math.isclose(original['weekday_weekend_ratio'], statistical['daytype']['weekday_to_weekend_mean_ratio'], abs_tol=1e-10, rel_tol=0):
        raise AnalysisError('Recomputed weekday/weekend ratio mismatch')
    if not math.isclose(original['mean_evening_minus_morning_pp'], statistical['weekday_peak']['mean_daily_evening_minus_morning_pp'], abs_tol=1e-8, rel_tol=0):
        raise AnalysisError('Recomputed weekday peak-share result mismatch')
    if day_entries[EXCLUDED_DATE] != 3104249:
        raise AnalysisError('The preselected October 14 date does not match source evidence')
    table_dir = Path(table_dir)
    report_dir = Path(report_dir)
    output_dir = Path(output_dir)
    for path in (table_dir, report_dir, output_dir):
        path.mkdir(parents=True, exist_ok=True)
    table_path = table_dir / 'weekday_date_sensitivity.csv'
    with table_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(original))
        writer.writeheader()
        writer.writerows([original, excluded])
    ratio_change = excluded['weekday_weekend_ratio'] - original['weekday_weekend_ratio']
    pp_change = excluded['mean_evening_minus_morning_pp'] - original['mean_evening_minus_morning_pp']
    report_path = report_dir / 'october_date_sensitivity.md'
    report_path.write_text('\n'.join([
        '# October 14 exclusion sensitivity — station entry analysis',
        '',
        '**Author:** Cyril James Lunzaga',
        '**Source:** Official MTA station-complex estimated entries, October 2024.',
        '',
        '## Scope and rationale',
        '',
        'October 14 is the lowest observed October weekday by systemwide estimated entries. This is a preselected one-date omission to assess stability, not a claim that the record is invalid. No cause is inferred.',
        '',
        '## Recomputed comparisons',
        '',
        f'- All 23 weekdays and 8 weekend dates: weekday/weekend mean ratio **{original["weekday_weekend_ratio"]:.4f}**, mean evening-minus-morning entry share **{original["mean_evening_minus_morning_pp"]:+.4f} percentage points**.',
        f'- Excluding 2024-10-14 (22 weekdays and 8 weekend dates): ratio **{excluded["weekday_weekend_ratio"]:.4f}**, mean difference **{excluded["mean_evening_minus_morning_pp"]:+.4f} percentage points**.',
        f'- Shift in ratio: **{ratio_change:+.4f}**; shift in mean evening-minus-morning share: **{pp_change:+.4f} percentage points**.',
        f'- Both comparisons remain positive under the exclusion: **{excluded["evening_greater_weekdays"]} of 22** retained weekdays have greater evening than morning entry shares.',
        '',
        '## Statistical limits',
        '',
        'The reported 95% percentile intervals use 10,000 independent-within-day-type bootstrap resamples of calendar dates (seed 202410); the paired share difference resamples each retained weekday as a unit. These intervals characterize date-to-date variation in this one month under the resampling assumptions, not long-run uncertainty, causality, service reliability, or occupancy. The sensitivity changes the analysis sample rather than repairing source data.',
        '',
        'A single unusual weekday may influence the magnitude of a reported comparison; report the complete-month results as primary and the exclusion as sensitivity only.',
    ]) + '\n', encoding='utf-8', newline='\n')
    manifest = {
        'status': 'passed',
        'source_csv_sha256': SOURCE_SHA256,
        'source_month': '2024-10',
        'excluded_date': EXCLUDED_DATE,
        'bootstrap_unit': 'calendar day',
        'bootstrap_replications': REPS,
        'bootstrap_seed': SEED,
        'baseline': original,
        'exclusion': excluded,
        'weekday_weekend_ratio_change': ratio_change,
        'evening_minus_morning_pp_change': pp_change,
        'artifacts': {
            'table': {'path': table_path.as_posix(), 'sha256': file_sha256(table_path), 'rows': 2},
            'report': {'path': report_path.as_posix(), 'sha256': file_sha256(report_path)},
        },
    }
    write_json_atomic(output_dir / 'sensitivity_manifest.json', manifest)
    return manifest


def main():
    try:
        files, statistical, _ = verify_inputs()
        report = write_outputs(_read_table(files['calendar_day_entries']), _read_table(files['weekday_peak_day_pairs']), statistical)
    except (AnalysisError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'STOP - Sensitivity analysis not approved: {exc}')
        return 2
    print('PASS - Source-linked, preselected October 14 sensitivity')
    print('Baseline weekday/weekend ratio:', round(report['baseline']['weekday_weekend_ratio'], 6))
    print('Exclusion weekday/weekend ratio:', round(report['exclusion']['weekday_weekend_ratio'], 6))
    print('Baseline evening-minus-morning pp:', round(report['baseline']['mean_evening_minus_morning_pp'], 6))
    print('Exclusion evening-minus-morning pp:', round(report['exclusion']['mean_evening_minus_morning_pp'], 6))
    print('PASS - Two-row comparison table, report and SHA-256 manifest created')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
