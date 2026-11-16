import tempfile
import unittest
from pathlib import Path

from commuter_rush.temporal_analysis import AnalysisError, file_sha256
from commuter_rush.verify_evidence import validated_artifact


class EvidenceVerificationTests(unittest.TestCase):
    def test_artifact_fingerprints_reject_tampered_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.csv'
            path.write_text('study_rows\n2\n', encoding='utf-8')
            digest = file_sha256(path)
            self.assertEqual(validated_artifact(path, digest), path)
            path.write_text('study_rows\n3\n', encoding='utf-8')
            with self.assertRaises(AnalysisError):
                validated_artifact(path, digest)


if __name__ == '__main__':
    unittest.main()
