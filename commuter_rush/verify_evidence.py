from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np

from commuter_rush.temporal_analysis import AnalysisError, SOURCE_CSV, file_sha256, verify_source

OUTPUT_DIRECTORY = Path('outputs/statistical_evidence')
TEMPORAL_OUTPUT_DIRECTORY = Path('outputs/temporal_analysis')
REVIEW_BUNDLE = OUTPUT_DIRECTORY / 'phase04_review_bundle.zip'


def validated_artifact(path, expected_hash, expected_bytes=None):
    path = Path(path)
    if not path.is_file() or file_sha256(path) != expected_hash:
        raise AnalysisError(f'Analytical artifact missing or altered: {path.as_posix()}')
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise AnalysisError(f'Analytical artifact byte length mismatch: {path.as_posix()}')
    return path


def read_json(path):
    path = Path(path)
    if not path.is_file():
        raise AnalysisError(f'Required evidence manifest missing: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def verify_and_bundle(destination=REVIEW_BUNDLE):
    source = verify_source()
    data_hash = file_sha256(SOURCE_CSV)
    descriptive = read_json(TEMPORAL_OUTPUT_DIRECTORY / 'descriptive_summary.json')
    temporal_tables = read_json(TEMPORAL_OUTPUT_DIRECTORY / 'descriptive_artifacts.json')
    temporal_figures = read_json(TEMPORAL_OUTPUT_DIRECTORY / 'visual_artifacts.json')
    evidence = read_json(OUTPUT_DIRECTORY / 'statistical_summary.json')
    orientation = read_json(OUTPUT_DIRECTORY / 'station_orientation_summary.json')
    figures = read_json(OUTPUT_DIRECTORY / 'statistical_figure_manifest.json')
    if (data_hash != source['processed_csv']['sha256']
            or any(item.get('source_csv_sha256') != data_hash for item in (
                descriptive, temporal_tables, evidence, orientation, figures,
            ))):
        raise AnalysisError('Analytical output source fingerprints differ')
    if (descriptive['observed_station_hours'] != 310187
            or descriptive['observed_station_complexes'] != 424
            or int(descriptive['estimated_entries']) != 114680137
            or evidence['daytype']['weekday_days'] != 23
            or evidence['daytype']['weekend_days'] != 8
            or evidence['weekday_peak']['observed_weekdays'] != 23
            or orientation['station_complexes'] != 424):
        raise AnalysisError('Published evidence does not match the reviewed October study')
    if evidence['bootstrap_replications'] != 10000 or evidence['bootstrap_seed'] != 202410:
        raise AnalysisError('Unreviewed resampling configuration')
    if not 0 <= orientation['primary_eligible_stations'] <= 424:
        raise AnalysisError('Invalid typology eligibility count')
    if sum(orientation['orientation_counts'].values()) != 424:
        raise AnalysisError('Station orientation inventory is incomplete')
    check = [
        evidence['daytype']['ratio_ci_low'],
        evidence['daytype']['ratio_ci_high'],
        evidence['weekday_peak']['mean_difference_ci_low'],
        evidence['weekday_peak']['mean_difference_ci_high'],
        evidence['manhattan_outer_contrast']['difference_ci_low'],
        evidence['manhattan_outer_contrast']['difference_ci_high'],
    ]
    if not np.isfinite(check).all():
        raise AnalysisError('Nonfinite uncertainty intervals')
    if (len(temporal_tables['tables']) != 10 or len(temporal_figures['figures']) != 6
            or len(evidence['table_artifacts']) != 5 or len(orientation['table_artifacts']) != 2
            or len(figures['images']) != 3 or len(figures['tables']) != 7):
        raise AnalysisError('Unexpected curated research artifact inventory')
    paths = []
    for manifest in [temporal_tables['tables'], evidence['table_artifacts'], orientation['table_artifacts']]:
        for item in manifest.values():
            paths.append(validated_artifact(item['path'], item['sha256']))
    for manifest in [temporal_figures['figures'], figures['images']]:
        for item in manifest.values():
            path = validated_artifact(item['path'], item['sha256'], item['bytes'])
            if not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                raise AnalysisError(f'Invalid figure signature: {path}')
            paths.append(path)
    for item in [temporal_tables['report'], figures['report']]:
        paths.append(validated_artifact(item['path'], item['sha256']))
    if len({str(path) for path in paths}) != 28:
        raise AnalysisError('Unexpected duplicate evidence filenames')
    documents = [
        TEMPORAL_OUTPUT_DIRECTORY / 'descriptive_summary.json',
        TEMPORAL_OUTPUT_DIRECTORY / 'descriptive_artifacts.json',
        TEMPORAL_OUTPUT_DIRECTORY / 'visual_artifacts.json',
        OUTPUT_DIRECTORY / 'statistical_summary.json',
        OUTPUT_DIRECTORY / 'station_orientation_summary.json',
        OUTPUT_DIRECTORY / 'statistical_figure_manifest.json',
    ]
    paths.extend(documents)
    destination = Path(destination)
    if destination.exists():
        raise AnalysisError(f'Existing review ZIP requires review: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(paths):
            archive.write(path, arcname=path.as_posix())
    return {
        'review_zip': destination.as_posix(),
        'review_zip_sha256': file_sha256(destination),
        'review_zip_bytes': destination.stat().st_size,
        'curated_tables': 17,
        'curated_figures': 9,
        'research_reports': 2,
        'source_sha256': data_hash,
        'primary_eligible_stations': orientation['primary_eligible_stations'],
        'stable_orientation_share_pct': orientation['stable_orientation_share_pct'],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.parse_args(argv)
    result = verify_and_bundle()
    print('PASS - Reviewed source, all 17 tables, 9 PNG figures, and 2 reports')
    print('PASS - Genuine October source fingerprints and statistical output reconciled')
    for key, value in result.items():
        print(f'{key}: {value}')
    print('VISUAL SIGNOFF PENDING USER-SUPPLIED REVIEW BUNDLE')


if __name__ == '__main__':
    main()
