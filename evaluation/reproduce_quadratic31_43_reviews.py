"""Replay completed source-reader reviews without replacing parallel reviewers.

The first helper's untouched source owns B31. The next frozen helper owns three
other peer reviews and preserves any independent judgment already at arm root.
No actual provider, runner, owner test rows or original report edits are used.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import review_pilot_quadratic31_43_v2 as baseline_reader
from evaluation import review_pilot_quadratic31_43_v3 as peer_reader
from evaluation.review_partial_upstream import write_once as original_write_once


def canonical_write_once(path, value):
    """JSON-equivalent tuple/list canonicalization for unchanged archived helpers.

    The pinned readers constructed proposal grids as Python tuples; their JSON
    output stores lists. Their legacy equality guard compares before encoding.
    This bridge changes storage comparison only, never a reviewed quantity or
    classification, and is separate from the immutable original helper bytes.
    """
    return original_write_once(path, json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False)))


if __name__ == "__main__":
    baseline_reader.write_once = canonical_write_once
    peer_reader.write_once = canonical_write_once
    baseline_reader.review_case(31, "B")
    for seed, arm in ((31, "C"), (43, "B"), (43, "C")):
        peer_reader.review_case(seed, arm)
