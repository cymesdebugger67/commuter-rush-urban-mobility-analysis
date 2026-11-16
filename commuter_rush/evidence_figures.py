from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from commuter_rush.temporal_analysis import AnalysisError, SOURCE_CSV, file_sha256, write_json_atomic

TABLE_DIRECTORY = Path('portfolio/tables')
FIGURE_DIRECTORY = Path('portfolio/figures')
OUTPUT_DIRECTORY = Path('outputs/statistical_evidence')
BLUE = '#22577A'
ORANGE = '#DB7731'
TEAL = '#278C88'
INK = '#20313E'


def save(name, fig, directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{name}.png'
    fig.savefig(path, dpi=160, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


def borough_interval_figure(borough, directory):
    data = borough.sort_values('mean_daily_evening_minus_morning_pp')
    y = np.arange(len(data))
    center = data['mean_daily_evening_minus_morning_pp'].to_numpy(dtype=float)
    low = data['difference_ci_low'].to_numpy(dtype=float)
    high = data['difference_ci_high'].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(9, 4.3))
    ax.errorbar(center, y, xerr=np.vstack([center - low, high - center]), fmt='o', color=INK,
                capsize=5, markersize=8, linewidth=2)
    ax.axvline(0, color='#7E8A93', linestyle='--', linewidth=1)
    ax.set_yticks(y, data['borough'])
    ax.set_xlabel('Evening minus morning entry share (percentage points)')
    ax.set_title('Day-level borough peak imbalance | October 2024', loc='left', color=INK, pad=15)
    ax.text(0, -.22, 'Points: mean of 23 weekday contrasts. Bars: 95% day-resampling intervals.',
            transform=ax.transAxes, fontsize=9, color='#536674')
    ax.spines[['right', 'top', 'left']].set_visible(False)
    ax.grid(axis='x', color='#E7EBEF')
    fig.tight_layout()
    return save('borough_peak_difference_intervals', fig, directory)


def orientation_figure(borough, directory):
    order = ['Bronx', 'Brooklyn', 'Queens', 'Manhattan']
    orientation = ['morning-oriented', 'balanced', 'evening-oriented']
    pivot = borough.pivot(index='borough', columns='orientation', values='share_of_eligible_borough_stations_pct')
    pivot = pivot.reindex(index=order, columns=orientation).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5))
    left = np.zeros(len(pivot))
    for label, color in zip(orientation, [BLUE, '#99A5AA', ORANGE]):
        values = pivot[label].to_numpy(dtype=float)
        ax.barh(np.arange(len(pivot)), values, left=left, label=label.replace('-', ' '), color=color, height=.65)
        left += values
    ax.set_yticks(np.arange(len(pivot)), order)
    ax.set_xlim(0, 100)
    ax.set_xlabel('Share of eligible station complexes (%)')
    ax.set_title('Station entry-window orientations by borough', loc='left', color=INK, pad=15)
    ax.legend(frameon=False, loc='upper center', bbox_to_anchor=(.5, -.16), ncol=3)
    ax.spines[['right', 'top', 'left']].set_visible(False)
    ax.grid(axis='x', color='#E7EBEF')
    ax.set_axisbelow(True)
    fig.tight_layout()
    return save('station_peak_orientation_by_borough', fig, directory)


def daytype_figure(daily, directory):
    weekdays = daily.loc[daily['day_type'].eq('Weekday'), 'estimated_entries'].to_numpy(dtype=float) / 1e6
    weekends = daily.loc[daily['day_type'].eq('Weekend'), 'estimated_entries'].to_numpy(dtype=float) / 1e6
    if len(weekdays) != 23 or len(weekends) != 8:
        raise AnalysisError('Unverified day-type table for figure')
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    ax.boxplot([weekdays, weekends], positions=[1, 2], widths=.45, showfliers=False,
               patch_artist=True, boxprops={'facecolor': '#DCECF5', 'edgecolor': INK},
               medianprops={'color': ORANGE, 'linewidth': 2})
    rng = np.random.default_rng(202410)
    for index, (values, color) in enumerate(((weekdays, BLUE), (weekends, TEAL)), start=1):
        ax.scatter(index + rng.uniform(-.13, .13, size=len(values)), values,
                   color=color, alpha=.75, s=35, zorder=3)
    ax.set_xticks([1, 2], ['Weekday (23)', 'Weekend (8)'])
    ax.set_ylabel('Daily estimated subway entries (millions)')
    ax.set_title('Day-level entry distributions | October 2024', loc='left', color=INK, pad=15)
    ax.spines[['right', 'top']].set_visible(False)
    ax.grid(axis='y', color='#E7EBEF')
    ax.set_axisbelow(True)
    fig.tight_layout()
    return save('weekday_weekend_day_distribution', fig, directory)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    required = {
        'borough_peak_uncertainty': 'borough_peak_uncertainty.csv',
        'borough_station_orientation': 'borough_station_orientation.csv',
        'calendar_day_entries': 'calendar_day_entries.csv',
    }
    for key, file in required.items():
        if not (TABLE_DIRECTORY / file).is_file():
            raise AnalysisError(f'Required statistical table missing: {file}')
    source = json.loads((OUTPUT_DIRECTORY / 'statistical_summary.json').read_text(encoding='utf-8'))
    orientation = json.loads((OUTPUT_DIRECTORY / 'station_orientation_summary.json').read_text(encoding='utf-8'))
    if (source['source_csv_sha256'] != orientation['source_csv_sha256']
            or source['source_csv_sha256'] != file_sha256(SOURCE_CSV)):
        raise AnalysisError('Statistical and station analysis source fingerprints differ')
    combined_table_artifacts = {**source['table_artifacts'], **orientation['table_artifacts']}
    if len(combined_table_artifacts) != 7:
        raise AnalysisError('Expected seven source-linked evidence tables')
    for name, evidence in combined_table_artifacts.items():
        path = Path(evidence['path'])
        if not path.is_file() or file_sha256(path) != evidence['sha256']:
            raise AnalysisError(f'Evidence table missing or altered: {name}')
        if len(pd.read_csv(path)) != evidence['rows']:
            raise AnalysisError(f'Evidence table row count differs: {name}')
    images = [
        borough_interval_figure(pd.read_csv(TABLE_DIRECTORY / required['borough_peak_uncertainty']), FIGURE_DIRECTORY),
        orientation_figure(pd.read_csv(TABLE_DIRECTORY / required['borough_station_orientation']), FIGURE_DIRECTORY),
        daytype_figure(pd.read_csv(TABLE_DIRECTORY / required['calendar_day_entries']), FIGURE_DIRECTORY),
    ]
    report_dir = Path('portfolio/reports')
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'october_statistical_evidence.md'
    day = source['daytype']
    peak = source['weekday_peak']
    contrast = source['manhattan_outer_contrast']
    lines = [
        '# October 2024 subway entry patterns — statistical evidence',
        '',
        '**Author:** Cyril James Lunzaga',
        '**Data owner:** Metropolitan Transportation Authority',
        '**Source:** [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)',
        '',
        '## Day-level variation',
        '',
        f"Observed mean daily weekday entries were {day['mean_weekday_entries']:,.0f}, compared with {day['mean_weekend_entries']:,.0f} on weekends.",
        f"The weekday/weekend ratio was {day['weekday_to_weekend_mean_ratio']:.2f}, with a 95% within-month day-resampling interval [{day['ratio_ci_low']:.2f}, {day['ratio_ci_high']:.2f}].",
        '',
        '## Rush-hour timing',
        '',
        f"Across {peak['observed_weekdays']} observed weekdays, evening minus morning share averaged {peak['mean_daily_evening_minus_morning_pp']:.2f} percentage points per weekday (95% day-resampling interval [{peak['mean_difference_ci_low']:.2f}, {peak['mean_difference_ci_high']:.2f}]).",
        f"Evening entries exceeded morning entries on {peak['weekdays_evening_greater_than_morning']} of those days.",
        f"Manhattan's day-level evening-minus-morning imbalance exceeded that of the combined Bronx, Brooklyn, and Queens by {contrast['mean_manhattan_minus_other_boroughs_pp']:.2f} percentage points on average (95% day-resampling interval [{contrast['difference_ci_low']:.2f}, {contrast['difference_ci_high']:.2f}]).",
        '',
        '## Station peak orientation',
        '',
        f"{orientation['primary_eligible_stations']} of {orientation['station_complexes']} station complexes met the predeclared 90% peak-hour coverage threshold.",
        f"Among {orientation['eligible_in_both_windows']} stations eligible under primary and alternative equal-length windows, {orientation['stable_orientation_share_pct'] if orientation['stable_orientation_share_pct'] is not None else float('nan'):.1f}% kept the same orientation label.",
        f"Orientation counts: {', '.join(f'{key}={value}' for key, value in sorted(orientation['orientation_counts'].items()))}.",
        '',
        '## Interpretation and limits',
        '',
        'These are estimated fare-paid station entries, not individual commuter trips, crowding, train loads, or station-to-station journeys. Date resampling describes variability within one historical month; its intervals are not forecasts or causal evidence. Time dependence, holidays, and changes in service are not controlled. Typology thresholds and alternative time windows are explicitly conventional. Missing station-hours are not imputed as zero, and representative coordinates remain nonauthoritative.',
    ]
    report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    manifest = {
        'source_csv_sha256': source['source_csv_sha256'],
        'tables': combined_table_artifacts,
        'report': {'path': report_path.as_posix(), 'sha256': file_sha256(report_path)},
        'images': {
            image.stem: {'path': image.as_posix(), 'bytes': image.stat().st_size, 'sha256': file_sha256(image)}
            for image in images
        },
    }
    write_json_atomic(OUTPUT_DIRECTORY / 'statistical_figure_manifest.json', manifest)
    print('PASS - Seven evidence tables and new statistical report verified')
    print('PASS - Three statistical figures rendered and fingerprinted')
    for image in images:
        print(image.as_posix(), image.stat().st_size)


if __name__ == '__main__':
    main()
