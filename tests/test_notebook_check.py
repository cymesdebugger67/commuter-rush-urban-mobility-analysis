import json
import tempfile
import unittest
from pathlib import Path

from commuter_rush.notebook_check import load_notebook, run_cells
from commuter_rush.temporal_analysis import AnalysisError


class NotebookCheckTests(unittest.TestCase):
    def test_project_notebook_inventory_and_syntax(self):
        cells = load_notebook()
        codes = [cell for cell in cells if cell['cell_type'] == 'code']
        self.assertEqual(len(codes), 6)
        for index, cell in enumerate(codes):
            compile(''.join(cell['source']), f'notebook_cell_{index}', 'exec')

    def test_code_cells_execute_in_order(self):
        cells = [
            {'cell_type': 'markdown', 'source': ['Purpose']},
            {'cell_type': 'code', 'source': ['counter = 4']},
            {'cell_type': 'code', 'source': ['counter += 2']},
        ]
        count, state = run_cells(cells)
        self.assertEqual(count, 2)
        self.assertEqual(state['counter'], 6)

    def test_bad_notebook_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.ipynb'
            path.write_text(json.dumps({'nbformat': 3, 'cells': []}), encoding='utf-8')
            with self.assertRaises(AnalysisError):
                load_notebook(path)


if __name__ == '__main__':
    unittest.main()
