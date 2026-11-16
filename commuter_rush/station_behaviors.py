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
    file_sha256,
    representative_station_labels,
    validated_frame,
    verify_source,
    write_json_atomic,
)

OUTPUT_DIRECTORY = Path('outputs/statistical_evidence')
PRIMARY_MORNING = (7, 8, 9)
PRIMARY_EVENING = (16, 17, 18)
ALTERNATE_MORNING = (6, 7, 8, 9)
ALTERNATE_EVENING = (15, 16, 17, 18)
MINIMUM_COVERAGE = .90
BALANCE_THRESHOLD = .15


def classify_peak_balance(index, threshold=BALANCE_THRESHOLD):
    if not np.isfinite(index) or threshold <= 0 or threshold >= 1:
        raise AnalysisError('Peak balance index or orientation threshold invalid')
    if index < -threshold:
        return 'morning-oriented'
    if index > threshold:
        return 'evening-oriented'
    return 'balanced'


def window_balance(frame, morning, evening, n_weekdays):
    if not set(morning).isdisjoint(evening) or len(morning) != len(evening):
        raise AnalysisError('Peak windows must be disjoint and equally long')
    weekday = frame.loc[frame['day_type'].eq('Weekday')]
    stations = sorted(frame['station_complex_id'].astype(str).unique())
    rows = []
    for label, hours in [('morning', morning), ('evening', evening)]:
        subset = weekday.loc[weekday['hour'].isin(hours)]
        grouped = subset.groupby('station_complex_id', observed=True).agg(
            entries=('estimated_entries', 'sum'),
            observed_hours=('timestamp', 'nunique'),
        )
        grouped.index = grouped.index.astype(str)
        grouped = grouped.reindex(stations)
        grouped.columns = [f'{label}_{name}' for name in grouped.columns]
        rows.append(grouped)
    table = pd.concat(rows, axis=1).reset_index(names=['station_complex_id'])
    for period in ('morning', 'evening'):
        table[f'{period}_coverage_pct'] = 100 * table[f'{period}_observed_hours'] / (n_weekdays * len(morning))
    table['eligible'] = (
        table[['morning_coverage_pct', 'evening_coverage_pct']].ge(100 * MINIMUM_COVERAGE).all(axis=1)
        & table[['morning_entries', 'evening_entries']].notna().all(axis=1)
        & (table['morning_entries'] + table['evening_entries'] > 0)
    )
    denominator = table['morning_entries'] + table['evening_entries']
    table['balance_index'] = np.where(
        table['eligible'], (table['evening_entries'] - table['morning_entries']) / denominator, np.nan,
    )
    table['orientation'] = table['balance_index'].map(
        lambda value: classify_peak_balance(value) if pd.notna(value) else 'not_eligible'
    )
    return table


def station_typologies(frame, source_hash=None):
    weekdays = sorted(frame.loc[frame['day_type'].eq('Weekday'), 'date'].unique())
    if len(weekdays) != 23:
        raise AnalysisError('Expected 23 October weekdays for station typologies')
    primary = window_balance(frame, PRIMARY_MORNING, PRIMARY_EVENING, 23)
    alternative = window_balance(frame, ALTERNATE_MORNING, ALTERNATE_EVENING, 23)
    labels = representative_station_labels(frame)
    labels['station_complex_id'] = labels['station_complex_id'].astype(str)
    primary = primary.merge(labels, on='station_complex_id', validate='one_to_one')
    if len(primary) != frame['station_complex_id'].nunique():
        raise AnalysisError('Station-level data lost identifiers')
    alternate = alternative[['station_complex_id', 'eligible', 'orientation', 'balance_index']].rename(
        columns={
            'eligible': 'eligible_alternative',
            'orientation': 'orientation_alternative',
            'balance_index': 'balance_index_alternative',
        }
    )
    result = primary.merge(alternate, on='station_complex_id', validate='one_to_one')
    result['orientation_stable'] = np.where(
        result['eligible'] & result['eligible_alternative'],
        result['orientation'].eq(result['orientation_alternative']),
        np.nan,
    )
    by_borough = (
        result.loc[result['eligible']]
        .groupby(['borough', 'orientation'], observed=True)
        .size().rename('station_complexes').reset_index()
    )
    borough_counts = result.loc[result['eligible']].groupby('borough', observed=True).size().rename('borough_eligible_stations')
    by_borough = by_borough.join(borough_counts, on='borough')
    by_borough['share_of_eligible_borough_stations_pct'] = 100 * (
        by_borough['station_complexes'] / by_borough['borough_eligible_stations']
    )
    stable = result.loc[result['eligible'] & result['eligible_alternative'], 'orientation_stable'].dropna()
    summary = {
        'source_csv_sha256': source_hash,
        'station_complexes': len(result),
        'primary_eligible_stations': int(result['eligible'].sum()),
        'alternative_eligible_stations': int(result['eligible_alternative'].sum()),
        'eligible_in_both_windows': len(stable),
        'stable_orientation_share_pct': float(stable.mean() * 100) if len(stable) else None,
        'balance_threshold': BALANCE_THRESHOLD,
        'primary_morning_hours': list(PRIMARY_MORNING),
        'primary_evening_hours': list(PRIMARY_EVENING),
        'alternative_morning_hours': list(ALTERNATE_MORNING),
        'alternative_evening_hours': list(ALTERNATE_EVENING),
        'minimum_coverage_pct': MINIMUM_COVERAGE * 100,
        'orientation_counts': {str(k): int(v) for k, v in result['orientation'].value_counts().items()},
    }
    return result, by_borough, summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    source = verify_source()
    frame = validated_frame(SOURCE_CSV, source)
    stations, boroughs, summary = station_typologies(frame, source_hash=file_sha256(SOURCE_CSV))
    TABLE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    stations.to_csv(TABLE_DIRECTORY / 'station_peak_orientation.csv', index=False, float_format='%.12g')
    boroughs.to_csv(TABLE_DIRECTORY / 'borough_station_orientation.csv', index=False, float_format='%.12g')
    summary['table_artifacts'] = {
        name: {'path': (TABLE_DIRECTORY / f'{name}.csv').as_posix(),
               'rows': len(table), 'sha256': file_sha256(TABLE_DIRECTORY / f'{name}.csv')}
        for name, table in [('station_peak_orientation', stations), ('borough_station_orientation', boroughs)]
    }
    write_json_atomic(OUTPUT_DIRECTORY / 'station_orientation_summary.json', summary)
    print('PASS - Peak orientations computed without missing-hour zero imputation')
    print('Primary eligible stations:', summary['primary_eligible_stations'])
    print('Primary/alternative category stability (%):', summary['stable_orientation_share_pct'])
    print('Orientation counts:', summary['orientation_counts'])


if __name__ == '__main__':
    main()
