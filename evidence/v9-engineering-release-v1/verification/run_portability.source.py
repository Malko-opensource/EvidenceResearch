"""Only the separately GO-authorized own-v9 portability child executes this."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

proof = Path(os.environ["ER_PROOF_ROOT"]).resolve()
release = Path(os.environ["ER_RELEASE_ROOT"]).resolve()
runtime_roots = {Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve()}
initial = list(sys.path)
runtime = [value for value in initial if value and any(Path(value).resolve().is_relative_to(root) for root in runtime_roots)]
sys.path[:] = [str(release)] + [value for value in runtime if value != str(release)]
(proof / "bootstrap-search-paths.json").write_text(json.dumps({
    "scope": "Own release plus interpreter runtime; the already loaded audit hook remains active.",
    "effective_sys_path": sys.path, "removed_nonruntime_paths": [value for value in initial if value not in sys.path]
}, indent=2) + "\n", encoding="utf-8")
inventory_path = Path(os.environ["ER_EXPECTED_TEST_INVENTORY"])
if hashlib.sha256(inventory_path.read_bytes()).hexdigest() != os.environ["ER_EXPECTED_TEST_INVENTORY_SHA256"]:
    raise ValueError("External portability inventory pin differs")
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
suite = unittest.TestSuite()
for filename in inventory["selected_filenames"]:
    suite.addTests(unittest.defaultTestLoader.discover("tests", pattern=filename))


def leaves(value):
    if isinstance(value, unittest.TestSuite):
        for member in value:
            yield from leaves(member)
    else:
        yield value


ids = [test.id() for test in leaves(suite)]
(proof / "discovered-test-ids.json").write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8")
if len(set(ids)) != len(ids) or sorted(ids) != inventory["test_ids"]:
    raise ValueError("Own-env discovery differs from exact selected AST inventory")
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
