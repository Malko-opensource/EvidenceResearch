"""Reuse the read-only observatory check with a separate client-view proof folder.

Arguments are parsed by the original checker: before|after, --base and
--require-assets. Historical proof and validation functions remain unchanged.
"""
from pathlib import Path
import importlib.util


CHECKER = Path(__file__).resolve().with_name("observatory_followup_check.py")
spec = importlib.util.spec_from_file_location("observatory_followup_check", CHECKER)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
checker.PROOF = (checker.PROJECT / "validation/client-spectator-20261004").resolve()
checker.BASELINE = checker.PROOF / "state-before.json"


if __name__ == "__main__":
    raise SystemExit(checker.main())
