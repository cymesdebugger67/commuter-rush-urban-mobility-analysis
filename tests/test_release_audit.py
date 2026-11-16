import tempfile
import unittest
from pathlib import Path

from commuter_rush.release_audit import validate_public_tree
from commuter_rush.temporal_analysis import AnalysisError


class ReleaseAuditTests(unittest.TestCase):
    def test_public_assets_and_legacy_source_removed(self):
        metadata = validate_public_tree()
        self.assertEqual(len(metadata['cover_sha256']), 64)
        self.assertEqual(len(metadata['readme_sha256']), 64)

    def test_legacy_readme_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'portfolio/assets').mkdir(parents=True)
            (root / 'docs').mkdir()
            (root / 'README.md').write_text('Bike-sharing capital bikeshare', encoding='utf-8')
            (root / 'analysis.py').write_text('print(1)', encoding='utf-8')
            (root / 'portfolio/assets/commuter_rush_cover.jpg').write_bytes(b'\xff\xd8\xff' + b'0' * 51000)
            for name in ('data_provenance.md', 'project_log.md'):
                (root / 'docs' / name).write_text('Cyril James Lunzaga', encoding='utf-8')
            with self.assertRaises(AnalysisError):
                validate_public_tree(root)


if __name__ == '__main__':
    unittest.main()
