"""Registration-source correctness only; no model or performance experiment."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.store import fingerprint
from evidence_research.study import register_pilot, check_pilot
from tests.test_study import settings


class PilotLiteratureReceiptTests(unittest.TestCase):
    def test_actual_five_paper_input_is_the_shared_receipt_not_the_default_three(self):
        corpus = json.loads((Path(__file__).resolve().parents[1] / "references" / "task_literature_v2.json").read_text(encoding="utf-8"))["records"]
        config = settings()
        config["resource_envelope"].update(literature_snapshot=corpus, literature_snapshot_sha256=fingerprint(corpus),
                                           upstream_settings={"num_papers_lit_review": 5})
        with tempfile.TemporaryDirectory() as temporary:
            receipt = register_pilot(config, Path(temporary) / "study")
            self.assertEqual(receipt["shared_literature_sha256"], fingerprint(corpus))
            self.assertEqual(receipt, check_pilot(Path(temporary) / "study"))

    def test_insufficient_or_changed_corpus_does_not_create_a_partial_registration(self):
        config = settings()
        config["resource_envelope"]["upstream_settings"] = {"num_papers_lit_review": 5}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "insufficient"
            with self.assertRaises(ValueError):
                register_pilot(config, root)
            self.assertFalse(root.exists())
            altered = copy.deepcopy(config)
            altered["resource_envelope"].update(literature_snapshot=[], literature_snapshot_sha256="invalid")
            with self.assertRaises(ValueError):
                register_pilot(altered, root)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
