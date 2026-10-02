"""Windows-length and immutable interrupted-snapshot fixtures; model calls zero."""
from pathlib import Path
import tempfile
import unittest

from evidence_research.evaluation import _validate_saved_score
from evidence_research.model import ModelUnavailable
from evidence_research.store import sha256_file
from evidence_research.study import _record_external_attempt, load


class InterruptedSnapshotTests(unittest.TestCase):
    def test_long_original_tree_preserved_as_short_blobs_with_original_map(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            arm = output / "units" / "quad-179" / "B"
            arm.mkdir(parents=True)
            source = arm
            while len(str(source.resolve())) < 200:
                source /= "nested-" + "x" * 35
            source.mkdir(parents=True)
            source /= "original-receipt.json"
            source.write_bytes(b'{"fixture":"preserve original completed receipt"}')
            original_sha = sha256_file(source)
            receipt = _record_external_attempt(output, arm, {"unit_id": "quad-179"}, "B", ModelUnavailable("explicit definitive fixture provider failure"))
            index = load(receipt.parent / "snapshot-map.json")
            entry = next(item for item in index["files"] if item["original_relative_path"] == source.relative_to(arm).as_posix())
            copied = receipt.parent / entry["snapshot_relative_path"]
            self.assertLess(len(str(copied.resolve())), len(str(source.resolve())))
            self.assertEqual(copied.read_bytes(), source.read_bytes())
            self.assertEqual(entry["sha256"], original_sha)
            self.assertEqual(sha256_file(source), original_sha)
            score = load(receipt)
            _validate_saved_score(score, {}, receipt.parent)
            # Continuing live work cannot alter the durable interrupted snapshot.
            source.write_bytes(b'changed live fixture after snapshot')
            _validate_saved_score(score, {}, receipt.parent)
            copied.write_bytes(b'tampered immutable snapshot')
            with self.assertRaisesRegex(ValueError, "completed failure evidence changed"):
                _validate_saved_score(score, {}, receipt.parent)


if __name__ == "__main__":
    unittest.main()
