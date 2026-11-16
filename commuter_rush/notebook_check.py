from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from commuter_rush.temporal_analysis import AnalysisError, write_json_atomic

NOTEBOOK = Path('notebooks/commuter_rush_case_study.ipynb')
OUTPUT = Path('outputs/release_readiness/notebook_execution.json')
EXPECTED_SOURCE_SHA256 = '0f74ac842c268e9599485caca1b78c897867140fb976b9fa4e0b1d21b51945eb'


def load_notebook(path=NOTEBOOK):
    path = Path(path)
    if not path.is_file():
        raise AnalysisError(f'Notebook missing: {path}')
    document = json.loads(path.read_text(encoding='utf-8'))
    cells = document.get('cells', [])
    if document.get('nbformat') != 4 or len(cells) < 9:
        raise AnalysisError('Unexpected case-study notebook structure')
    return cells


def run_cells(cells, namespace=None):
    state = {'__name__': '__main__', 'display': lambda value: print(value.to_string(index=False))}
    if namespace:
        state.update(namespace)
    count = 0
    for index, cell in enumerate(cells):
        kind = cell.get('cell_type')
        if kind not in {'markdown', 'code'}:
            raise AnalysisError(f'Unexpected notebook cell type at index {index}')
        if kind != 'code':
            continue
        source = cell.get('source', [])
        code = ''.join(source) if isinstance(source, list) else str(source)
        try:
            exec(compile(code, f'{NOTEBOOK.as_posix()}:cell_{index}', 'exec'), state)
        except Exception as exc:
            raise AnalysisError(f'Notebook execution failed at code cell {index}: {exc}') from exc
        finally:
            plt.close('all')
        count += 1
    return count, state


def main(argv=None):
    parser = argparse.ArgumentParser(description='Execute trusted project notebook code cells against the verified local source')
    parser.parse_args(argv)
    cells = load_notebook()
    count, state = run_cells(cells)
    if count != 6:
        raise AnalysisError('Notebook cell inventory differs from reviewed study')
    dataframe = state['frame']
    ratio = float(state['ratio'])
    pairs = state['paired']
    station = state['station']
    pp = float(pairs['evening_minus_morning_pp'].mean())
    categories = station['orientation'].value_counts().to_dict()
    if (len(dataframe) != 310187
            or abs(ratio - 1.674915811329054) > 0.00001
            or abs(pp - 3.079943813200393) > 0.00001
            or len(pairs) != 23 or len(station) != 424
            or categories != {'morning-oriented': 261, 'evening-oriented': 91, 'balanced': 72}):
        raise AnalysisError('Executed notebook findings disagree with reviewed October output')
    source = Path('data/processed/mta_subway_station_hour_october_2024.csv')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != EXPECTED_SOURCE_SHA256:
        raise AnalysisError('Executed notebook used a different data source')
    manifest = {
        'status': 'passed',
        'execution_type': 'sequential trusted notebook Python code cells via Python terminal (not Jupyter UI)',
        'notebook_path': NOTEBOOK.as_posix(),
        'notebook_sha256': hashlib.sha256(NOTEBOOK.read_bytes()).hexdigest(),
        'processed_csv_sha256': digest,
        'executed_code_cells': count,
        'observed_station_hours': len(dataframe),
        'weekday_weekend_ratio': ratio,
        'weekday_evening_minus_morning_pp': pp,
        'station_orientation_counts': categories,
    }
    write_json_atomic(OUTPUT, manifest)
    print(f'PASS - {count} notebook code cells executed against the reviewed October CSV')
    print(f'PASS - Notebook ratio: {ratio:.6f}; weekday peak difference: {pp:.6f} pp')
    print(f'PASS - Station orientation counts: {categories}')
    print(f'Notebook verification manifest: {OUTPUT.as_posix()}')


if __name__ == '__main__':
    main()
