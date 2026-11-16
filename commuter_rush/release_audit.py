from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from commuter_rush.temporal_analysis import AnalysisError, file_sha256, verify_source, write_json_atomic

OUTPUT = Path('outputs/release_readiness/release_audit.json')
EXPECTED_SOURCE_SHA256 = '0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb'
FORBIDDEN_TERMS = ('bike-sharing', 'capital bikeshare', 'weather-category comparisons', 'uci machine learning repository')


def validate_public_tree(root=Path('.')):
    root = Path(root)
    readme = root / 'README.md'
    cover = root / 'portfolio/assets/commuter_rush_cover.jpg'
    entry = root / 'analysis.py'
    if not readme.is_file() or not cover.is_file() or not entry.is_file():
        raise AnalysisError('README, cover, or root analysis entry point missing')
    contents = readme.read_text(encoding='utf-8')
    for term in ('Cyril James Lunzaga', 'wujg-7c2s', '114,680,137',
                 '310,187', '261', '91', '72', 'unspecified', 'source'):
        if term not in contents:
            raise AnalysisError(f'Public README is missing required attribution or context: {term}')
    if any(term in contents.lower() for term in FORBIDDEN_TERMS):
        raise AnalysisError('Old unrelated project claims found in README')
    if any(term in entry.read_text(encoding='utf-8').lower() for term in FORBIDDEN_TERMS):
        raise AnalysisError('Old unrelated entry point remains')
    if cover.stat().st_size < 50000 or not cover.read_bytes().startswith(b'\xff\xd8\xff'):
        raise AnalysisError('Cover image is missing or invalid')
    for path in (root / 'docs/data_provenance.md', root / 'docs/project_log.md'):
        if 'Cyril James Lunzaga' not in path.read_text(encoding='utf-8'):
            raise AnalysisError(f'Author attribution missing from {path}')
    return {'cover_sha256': file_sha256(cover), 'readme_sha256': file_sha256(readme)}


def validate_git_candidate_files():
    result = subprocess.run(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        capture_output=True, check=True,
    )
    files = sorted(set(Path(name.decode('utf-8')) for name in result.stdout.split(b'\0') if name))
    blocked_prefix = ('data/raw/', 'data/processed/', 'outputs/', '.venv/', '.git/')
    blocked_suffix = ('.env', '.pem', '.key', '.p12', '.pfx', '.zip', '.log', '.db')
    for path in files:
        name = path.as_posix()
        if name not in {'data/raw/.gitkeep', 'outputs/.gitkeep'} and (name.startswith(blocked_prefix) or name.endswith(blocked_suffix)):
            raise AnalysisError(f'Potential data, secret or archive leak in Git candidate list: {name}')
        if (name.endswith('.csv') and not name.startswith('portfolio/tables/')):
            raise AnalysisError(f'Noncurated CSV is included in Git candidate list: {name}')
        if (path.is_file() and path.suffix in {'.py', '.md', '.txt', '.ipynb'}):
            content = path.read_text(encoding='utf-8', errors='replace')
            if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16}', content):
                raise AnalysisError(f'Potential credential-like literal in {name}')
    ignore = Path('.gitignore').read_text(encoding='utf-8')
    for rule in ('.venv/', 'data/raw/*', 'data/processed/', 'outputs/*'):
        if rule not in ignore:
            raise AnalysisError(f'Missing Git exclusion rule: {rule}')
    return {'candidate_file_count': len(files), 'candidate_filenames': [path.as_posix() for path in files]}


def verified_artifacts():
    base = Path('outputs')
    temporal = json.loads((base / 'temporal_analysis/descriptive_artifacts.json').read_text(encoding='utf-8'))
    temporal_images = json.loads((base / 'temporal_analysis/visual_artifacts.json').read_text(encoding='utf-8'))
    statistics = json.loads((base / 'statistical_evidence/statistical_summary.json').read_text(encoding='utf-8'))
    orientation = json.loads((base / 'statistical_evidence/station_orientation_summary.json').read_text(encoding='utf-8'))
    figure_index = json.loads((base / 'statistical_evidence/statistical_figure_manifest.json').read_text(encoding='utf-8'))
    sensitivity = json.loads((base / 'release_readiness/sensitivity_manifest.json').read_text(encoding='utf-8'))
    notebook = json.loads((base / 'release_readiness/notebook_execution.json').read_text(encoding='utf-8'))
    for name, index in [('descriptive', temporal), ('statistical', statistics), ('orientation', orientation), ('sensitivity', sensitivity)]:
        if index['source_csv_sha256'] != EXPECTED_SOURCE_SHA256:
            raise AnalysisError(f'{name} artifacts refer to a different data source')
    if notebook['processed_csv_sha256'] != EXPECTED_SOURCE_SHA256 or notebook['status'] != 'passed':
        raise AnalysisError('Notebook execution evidence missing or inconsistent')
    records = []
    for mapping in (temporal['tables'], statistics['table_artifacts'], orientation['table_artifacts'],
                    temporal_images['figures'], figure_index['images']):
        for artifact in mapping.values():
            path = Path(artifact['path'])
            if not path.is_file() or file_sha256(path) != artifact['sha256']:
                raise AnalysisError(f'Artifact fingerprint mismatch: {path}')
            if 'bytes' in artifact and path.stat().st_size != artifact['bytes']:
                raise AnalysisError(f'Artifact length mismatch: {path}')
            records.append(path.as_posix())
    if len(records) != 26 or len(set(records)) != 26:
        raise AnalysisError('Expected 17 tables and 9 distinct figures')
    reports = (temporal['report'], figure_index['report'], sensitivity['artifacts']['report'])
    for artifact in reports:
        path = Path(artifact['path'])
        if not path.is_file() or file_sha256(path) != artifact['sha256']:
            raise AnalysisError(f'Findings report fingerprint mismatch: {path}')
    sensitivity_table = sensitivity['artifacts']['table']
    if file_sha256(sensitivity_table['path']) != sensitivity_table['sha256']:
        raise AnalysisError('Date sensitivity table fingerprint mismatch')
    if (statistics['weekday_peak']['observed_weekdays'] != 23
            or orientation['station_complexes'] != 424
            or sensitivity['baseline']['weekday_days'] != 23
            or sensitivity['exclusion']['weekday_days'] != 22):
        raise AnalysisError('Headline statistical counts differ')
    return {'tables': 18, 'figures': 9, 'reports': 3, 'reviewed_artifact_fingerprints': len(records) + 3 + 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only repository and real-output prepublication audit')
    parser.parse_args(argv)
    source = verify_source()
    if source['processed_csv']['sha256'] != EXPECTED_SOURCE_SHA256:
        raise AnalysisError('Reproduced source differs from the frozen October 2024 data')
    public = validate_public_tree()
    artifacts = verified_artifacts()
    candidates = validate_git_candidate_files()
    result = {
        'status': 'passed_prepublication_audit_not_git_release',
        'source_sha256': EXPECTED_SOURCE_SHA256,
        'observed_station_hours': source['month_quality']['station_hour_rows'],
        'observed_hours': source['month_quality']['observed_clock_hours'],
        'public_documents': public,
        'reviewed_artifacts': artifacts,
        'git_candidates': candidates,
        'limitations': 'Local numerical/source/file checks only; external publishing permissions and final staged Git diff require human review',
    }
    write_json_atomic(OUTPUT, result)
    print('PASS - MTA source SHA256, publication narrative and notebook execution evidence')
    print(f"PASS - {artifacts['tables']} tables, {artifacts['figures']} figures, {artifacts['reports']} reports")
    print(f"PASS - {candidates['candidate_file_count']} candidate Git files screened for unexpected data and credentials")
    print(f'Release audit manifest: {OUTPUT.as_posix()}')
    print('NOT YET APPROVED - Staged Git diff, remote publication and external release permissions')


if __name__ == '__main__':
    main()
