from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from commuter_rush.temporal_analysis import (
    AnalysisError,
    SOURCE_CSV,
    TABLE_DIRECTORY,
    REPORT_DIRECTORY,
    file_sha256,
    validated_frame,
    verify_source,
    write_json_atomic,
)

OUTPUT_DIRECTORY = Path('outputs/statistical_evidence')
MORNING = (7, 8, 9)
EVENING = (16, 17, 18)
SEED = 202410
BOOTSTRAP_REPLICATIONS = 10000


def percentile_interval(values, resamples=BOOTSTRAP_REPLICATIONS, seed=SEED):
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) < 2 or not np.isfinite(array).all():
        raise AnalysisError('Bootstrap requires at least two finite day-level observations')
    if resamples < 500:
        raise AnalysisError('Insufficient predeclared bootstrap replications')
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(array), size=(resamples, len(array)))
    draws = array[indices].mean(axis=1)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def daytype_uncertainty(frame, resamples=BOOTSTRAP_REPLICATIONS):
    daily = frame.groupby(['date', 'day_type'], as_index=False)['estimated_entries'].sum()
    weekdays = np.sort(daily.loc[daily['day_type'].eq('Weekday'), 'estimated_entries'].to_numpy(dtype=float))
    weekends = np.sort(daily.loc[daily['day_type'].eq('Weekend'), 'estimated_entries'].to_numpy(dtype=float))
    if len(weekdays) != 23 or len(weekends) != 8 or (weekdays <= 0).any() or (weekends <= 0).any():
        raise AnalysisError('Day-type sample does not match the frozen October study design')
    rng = np.random.default_rng(SEED)
    weekday_draws = weekdays[rng.integers(0, len(weekdays), size=(resamples, len(weekdays)))].mean(axis=1)
    weekend_draws = weekends[rng.integers(0, len(weekends), size=(resamples, len(weekends)))].mean(axis=1)
    difference = weekday_draws - weekend_draws
    ratio = weekday_draws / weekend_draws
    return pd.DataFrame([{
        'weekday_days': len(weekdays),
        'weekend_days': len(weekends),
        'mean_weekday_entries': float(weekdays.mean()),
        'mean_weekend_entries': float(weekends.mean()),
        'weekday_minus_weekend_mean_entries': float(weekdays.mean() - weekends.mean()),
        'difference_ci_low': float(np.quantile(difference, .025)),
        'difference_ci_high': float(np.quantile(difference, .975)),
        'weekday_to_weekend_mean_ratio': float(weekdays.mean() / weekends.mean()),
        'ratio_ci_low': float(np.quantile(ratio, .025)),
        'ratio_ci_high': float(np.quantile(ratio, .975)),
    }]), daily.sort_values('date').reset_index(drop=True)


def peak_day_evidence(frame, resamples=BOOTSTRAP_REPLICATIONS):
    weekday = frame.loc[frame['day_type'].eq('Weekday')].copy()
    weekday['period'] = np.select(
        [weekday['hour'].isin(MORNING), weekday['hour'].isin(EVENING)],
        ['morning', 'evening'], default='other',
    )
    daily_all = weekday.groupby('date')['estimated_entries'].sum().rename('all_entries')
    window_rows = weekday.loc[weekday['period'].ne('other')].groupby(['date', 'period'])['estimated_entries'].sum().unstack()
    paired = window_rows.join(daily_all)
    if (len(paired) != 23 or paired[['morning', 'evening', 'all_entries']].isna().any().any()
            or (paired['all_entries'] <= 0).any()):
        raise AnalysisError('Incomplete paired weekday demand observations')
    paired['morning_share_pct'] = 100 * paired['morning'] / paired['all_entries']
    paired['evening_share_pct'] = 100 * paired['evening'] / paired['all_entries']
    paired['evening_minus_morning_pp'] = paired['evening_share_pct'] - paired['morning_share_pct']
    paired = paired.reset_index().sort_values('date')
    low, high = percentile_interval(paired['evening_minus_morning_pp'], resamples=resamples)
    summary = {
        'observed_weekdays': len(paired),
        'mean_daily_evening_minus_morning_pp': float(paired['evening_minus_morning_pp'].mean()),
        'mean_difference_ci_low': low,
        'mean_difference_ci_high': high,
        'weekdays_evening_greater_than_morning': int((paired['evening'] > paired['morning']).sum()),
        'aggregate_morning_share_pct': float(100 * paired['morning'].sum() / paired['all_entries'].sum()),
        'aggregate_evening_share_pct': float(100 * paired['evening'].sum() / paired['all_entries'].sum()),
    }
    return paired, summary


def borough_peak_evidence(frame, resamples=BOOTSTRAP_REPLICATIONS):
    weekday = frame.loc[frame['day_type'].eq('Weekday')].copy()
    weekday['period'] = np.select(
        [weekday['hour'].isin(MORNING), weekday['hour'].isin(EVENING)],
        ['morning', 'evening'], default='other',
    )
    totals = weekday.groupby(['date', 'borough'])['estimated_entries'].sum().rename('all_entries')
    peak = weekday.loc[weekday['period'].ne('other')].groupby(
        ['date', 'borough', 'period'], observed=True,
    )['estimated_entries'].sum().unstack()
    paired = peak.join(totals).reset_index()
    if (paired[['morning', 'evening', 'all_entries']].isna().any().any() or (paired['all_entries'] <= 0).any()):
        raise AnalysisError('Missing borough-day peak observations')
    paired['morning_share_pct'] = 100 * paired['morning'] / paired['all_entries']
    paired['evening_share_pct'] = 100 * paired['evening'] / paired['all_entries']
    paired['evening_minus_morning_pp'] = paired['evening_share_pct'] - paired['morning_share_pct']
    boroughs = sorted(paired['borough'].unique())
    if boroughs != ['Bronx', 'Brooklyn', 'Manhattan', 'Queens']:
        raise AnalysisError('Borough inventory differs from October source')
    result = []
    for borough in boroughs:
        rows = paired.loc[paired['borough'].eq(borough)].sort_values('date')
        if len(rows) != 23 or rows['date'].nunique() != 23:
            raise AnalysisError(f'Incomplete borough weekday observations: {borough}')
        low, high = percentile_interval(rows['evening_minus_morning_pp'], resamples=resamples, seed=SEED)
        result.append({
            'borough': borough,
            'days': len(rows),
            'mean_daily_evening_minus_morning_pp': float(rows['evening_minus_morning_pp'].mean()),
            'difference_ci_low': low,
            'difference_ci_high': high,
            'aggregate_morning_share_pct': float(100 * rows['morning'].sum() / rows['all_entries'].sum()),
            'aggregate_evening_share_pct': float(100 * rows['evening'].sum() / rows['all_entries'].sum()),
            'evening_dominant_days': int((rows['evening'] > rows['morning']).sum()),
        })
    borough_result = pd.DataFrame(result)
    outer = paired.loc[paired['borough'].ne('Manhattan')].groupby('date', as_index=False)[
        ['morning', 'evening', 'all_entries']
    ].sum()
    outer['evening_minus_morning_pp'] = 100 * (outer['evening'] - outer['morning']) / outer['all_entries']
    manhattan = paired.loc[paired['borough'].eq('Manhattan'), ['date', 'evening_minus_morning_pp']]
    comparison = outer.merge(manhattan, on='date', validate='one_to_one', suffixes=('_outer', '_manhattan'))
    comparison['manhattan_minus_outer_pp'] = (
        comparison['evening_minus_morning_pp_manhattan'] - comparison['evening_minus_morning_pp_outer']
    )
    low, high = percentile_interval(comparison['manhattan_minus_outer_pp'], resamples=resamples)
    contrast = {
        'days': len(comparison),
        'mean_manhattan_minus_other_boroughs_pp': float(comparison['manhattan_minus_outer_pp'].mean()),
        'difference_ci_low': low,
        'difference_ci_high': high,
    }
    return borough_result, paired.sort_values(['date', 'borough']), contrast


def save_outputs(frame, output_dir=OUTPUT_DIRECTORY, table_dir=TABLE_DIRECTORY, report_dir=REPORT_DIRECTORY):
    output_dir = Path(output_dir)
    table_dir = Path(table_dir)
    report_dir = Path(report_dir)
    for directory in (output_dir, table_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)
    comparison, daily = daytype_uncertainty(frame)
    weekday, weekday_summary = peak_day_evidence(frame)
    borough, borough_daily, contrast = borough_peak_evidence(frame)
    tables = {
        'weekday_weekend_uncertainty': comparison,
        'calendar_day_entries': daily,
        'weekday_peak_day_pairs': weekday,
        'borough_peak_uncertainty': borough,
        'borough_peak_day_pairs': borough_daily,
    }
    for name, table in tables.items():
        table.to_csv(table_dir / f'{name}.csv', index=False, float_format='%.12g')
    summary = {
        'source_csv_sha256': file_sha256(SOURCE_CSV),
        'source_dataset_id': 'wujg-7c2s',
        'bootstrap_unit': 'calendar day',
        'bootstrap_replications': BOOTSTRAP_REPLICATIONS,
        'bootstrap_seed': SEED,
        'daytype': comparison.iloc[0].to_dict(),
        'weekday_peak': weekday_summary,
        'boroughs': borough.to_dict(orient='records'),
        'manhattan_outer_contrast': contrast,
    }
    summary['table_artifacts'] = {
        name: {'path': (table_dir / f'{name}.csv').as_posix(),
               'rows': len(table), 'sha256': file_sha256(table_dir / f'{name}.csv')}
        for name, table in tables.items()
    }
    write_json_atomic(output_dir / 'statistical_summary.json', summary)
    return summary, tables


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    source = verify_source()
    frame = validated_frame(SOURCE_CSV, source)
    summary, _ = save_outputs(frame)
    print('PASS - Day-level bootstrap estimates from reconciled October station-hours')
    print('PASS - Paired weekday and borough peak comparisons')
    print('Mean weekday / weekend daily ratio:', round(summary['daytype']['weekday_to_weekend_mean_ratio'], 4))
    print('Mean day-level evening minus morning (percentage points):', round(summary['weekday_peak']['mean_daily_evening_minus_morning_pp'], 4))
    print('Manhattan minus outer-borough peak contrast (percentage points):', round(summary['manhattan_outer_contrast']['mean_manhattan_minus_other_boroughs_pp'], 4))


if __name__ == '__main__':
    main()
