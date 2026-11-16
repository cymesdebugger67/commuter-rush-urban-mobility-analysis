import json
from pathlib import Path
import unittest


class NotebookStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path('notebooks/commuter_rush_case_study.ipynb')
        cls.book = json.loads(cls.path.read_text(encoding='utf-8'))

    def test_standard_format(self):
        self.assertEqual(self.book['nbformat'], 4)
        self.assertGreaterEqual(len(self.book['cells']), 9)
        self.assertTrue(any(cell['cell_type'] == 'code' for cell in self.book['cells']))

    def test_no_embedded_or_fake_outputs(self):
        for cell in self.book['cells']:
            if cell['cell_type'] == 'code':
                self.assertEqual(cell['outputs'], [])
                self.assertIsNone(cell['execution_count'])

    def test_source_verification_and_nonimputation_visible(self):
        text = '\n'.join(''.join(cell['source']) for cell in self.book['cells'])
        self.assertIn('hashlib.sha256(source.read_bytes())', text)
        self.assertIn('114680137', text)
        self.assertIn('not** imputed as zero', text)
        self.assertIn('Cyril James Lunzaga', text)

    def test_code_cells_compile(self):
        for cell in self.book['cells']:
            if cell['cell_type'] == 'code':
                compile(''.join(cell['source']), '<notebook-cell>', 'exec')
