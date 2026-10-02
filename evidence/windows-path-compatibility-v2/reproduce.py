"""Source-bound Windows path calculation and equal-length isolated I/O probes.

Never registers/runs a pilot or writes into either planned study output. This
checks path storage only, not a Codex invocation or complete CLI continuation.
"""
from pathlib import Path, PureWindowsPath
import ast
import hashlib
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SNAPSHOT = OUT / "source"
VALIDATION = ROOT / "evidence/checkpoint-replay-validation-v2"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def capture():
    receipt = OUT / "source-manifest.json"
    if not receipt.exists():
        source_files = [(VALIDATION / "source_snapshot/work/next-version/evidence_research" / name)
            for name in ("arms.py", "baseline.py", "comparison_arms.py", "model.py", "store.py", "study.py", "tasks.py")]
        source_files.append(ROOT / "examples/recommended-pilot-settings-v5.json")
        records = []
        for source in source_files:
            target = SNAPSHOT / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            expected = sha(source)
            shutil.copyfile(source, target)
            assert sha(source) == expected == sha(target)
            records.append({"source": str(source), "snapshot": target.name, "sha256": expected})
        write(receipt, {"scope": "Source-byte copies for Windows storage compatibility only", "files": records,
            "validation_manifest_sha256": sha(VALIDATION / "source-manifest.json")})
    records = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    for row in records:
        assert sha(SNAPSHOT / row["snapshot"]) == row["sha256"], "Pinned source modified"
    return records


def actual_atomic_json():
    tree = ast.parse((SNAPSHOT / "store.py").read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in ("canonical_json", "atomic_json")]
    assert {node.name for node in functions} == {"canonical_json", "atomic_json"}
    namespace = {"Path": Path, "os": os, "json": json, "Any": object}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SNAPSHOT / "store.py"), "exec"), namespace)
    return namespace["atomic_json"]


def main():
    records = capture()
    config = json.loads((SNAPSHOT / "recommended-pilot-settings-v5.json").read_text(encoding="utf-8-sig"))
    unit = max((row["unit_id"] for row in config["units"]), key=len)
    assert config["resource_envelope"]["proposal_calls_per_unit"] == 777
    assert config["resource_envelope"]["actual_cpu_executions_per_unit"] == 777
    source_text = {name: (SNAPSHOT / name).read_text(encoding="utf-8") for name in ("arms.py", "baseline.py", "study.py", "store.py")}
    assert '{self.logical_cursor:08d}-{digest(logical)[:12]}.json' in source_text["arms.py"]
    assert 'snapshot / f"{len(source_map):08d}.bin"' in source_text["study.py"]
    assert 'path.name + f".{os.getpid()}.tmp"' in source_text["store.py"]
    assert '{self.host_ordinal:08d}-{time.time_ns()}' in source_text["baseline.py"]
    # Ten digits conservatively cover a positive 32-bit process ID. The stage
    # timestamp uses 19 digits in the declared 2026 execution epoch. Components
    # are derived from registered IDs/resources and exact source format strings.
    pid = "9" * 10
    stamp = "9" * 19
    sha12, sha24 = "f" * 12, "f" * 24
    b = PureWindowsPath("units") / unit / "B"
    c = PureWindowsPath("units") / unit / "C"
    attempt = b / "attempts" / "attempt-0776"
    owner = b / "owner-attempts" / "attempt-0776"
    paths = {
        "B checkpoint staged cursor atomic temporary": attempt / "upstream/transport_checkpoints" / f".stage-00001554-{stamp}" / f"cursor.json.{pid}.tmp",
        "B checkpoint committed manifest atomic temporary": attempt / "upstream/transport_checkpoints" / f"00001554-{sha24}" / f"manifest.json.{pid}.tmp",
        "B checkpoint head atomic temporary": attempt / "upstream" / f"transport_checkpoint_head.json.{pid}.tmp",
        "B tool reply atomic temporary": attempt / "experiments/tool-replies" / f"00000776-{sha12}.json.{pid}.tmp",
        "B CPU source copy": attempt / "experiments/execution-0776/source/evidence_research/__init__.py",
        "B CPU independent verification": attempt / "experiments/execution-0776/independent_verification.json",
        "B model raw response": attempt / "model/upstream-0776/response.txt",
        "B no-action atomic receipt": attempt / "host-no-action" / f"upstream-0776.json.{pid}.tmp",
        "B owner flat preserved bytes": owner / "original-state/99999999.bin",
        "B owner immutable snapshot-map atomic temporary": owner / f"snapshot-map.json.{pid}.tmp",
        "B owner attempt receipt atomic temporary": owner / f"owner-attempt.json.{pid}.tmp",
        "B continuation lineage atomic temporary": b / "owner-continuation-lineages" / f"{sha24}.json.{pid}.tmp",
        "C CPU source copy": c / "research/evidence" / sha24 / "source/evidence_research/__init__.py",
        "C proposal observation atomic temporary": c / "resource-observations" / f"improved-0776.json.{pid}.tmp",
        "C failure lineage atomic temporary": c / "model-attempt-lineages" / f"{sha24}.json.{pid}.tmp",
        "C model raw response": c / "model/improved-0776/response.txt",
        "pilot source snapshot": PureWindowsPath("source-snapshot/evidence_research/comparison_arms.py"),
        "pilot owner public-data atomic temporary": PureWindowsPath("owner-development-data") / f"{unit}-public.json.{pid}.tmp",
    }
    # Preserve the source's old nested-copy risk as a counterfactual calculation
    # only. Current study.py uses the flat snapshot-map implementation instead.
    persisted = attempt / "upstream/transport_checkpoints" / f"00001554-{sha24}" / "manifest.json"
    paths["historical nested owner-copy counterfactual"] = owner / "original-state" / persisted.relative_to(b)
    release = PureWindowsPath(str(ROOT)) / "versions/v5-development"
    variants = {
        "planned long release output": release / "runs/development/recommended-pilot-v5",
        "planned short release output": release / "runs/p5",
    }
    atomic = actual_atomic_json()
    probe_root = ROOT / "work/wpv2/probes"
    probe_root.mkdir(parents=True, exist_ok=True)
    rows, probes = [], []
    for index, (variant, output) in enumerate(variants.items()):
        # A different owned directory with exactly the same root string length;
        # never make the real registration output non-empty.
        prefix = probe_root / f"v{index}"
        pad_length = len(str(output)) - len(str(prefix)) - 1
        assert pad_length > 0
        proxy = prefix / ("p" * pad_length)
        assert len(str(proxy)) == len(str(output))
        for name, relative in paths.items():
            target = output / relative
            proxy_target = proxy.joinpath(*relative.parts)
            assert len(str(proxy_target)) == len(str(target))
            item = {"variant": variant, "category": name, "absolute_path": str(target), "characters": len(str(target)),
                "individual_component_max": max(len(part) for part in target.parts), "under_260_character_legacy_limit": len(str(target)) < 260,
                "current_implementation_path": name != "historical nested owner-copy counterfactual"}
            rows.append(item)
            if name == "historical nested owner-copy counterfactual":
                continue
            # Probe the exact source atomic-json operation; the destination's
            # long temporary-file name is already represented in the template.
            # Use direct write for those .tmp templates to avoid adding a second
            # temporary suffix that the actual program does not create.
            try:
                proxy_target.parent.mkdir(parents=True, exist_ok=True)
                if name.endswith("atomic temporary") or "atomic receipt" in name:
                    with proxy_target.open("wb") as stream:
                        stream.write(b'{"fixture_only":true}\n')
                        stream.flush()
                        os.fsync(stream.fileno())
                    final_name = proxy_target.name.rsplit(f".{pid}.tmp", 1)[0]
                    os.replace(proxy_target, proxy_target.with_name(final_name))
                    observed = proxy_target.with_name(final_name)
                elif name == "B owner flat preserved bytes":
                    observed = proxy_target
                    seed = OUT / "fixture-bytes.bin"
                    seed.write_bytes(b"fixture bytes: original data identity is held by map\n")
                    shutil.copy2(seed, observed)
                    assert sha(seed) == sha(observed)
                else:
                    proxy_target.write_bytes(b"fixture-only path compatibility\n")
                    observed = proxy_target
                assert observed.is_file()
                status, error = "passed", None
            except OSError as exc:
                status, error = "failed", {"type": type(exc).__name__, "errno": exc.errno, "winerror": getattr(exc, "winerror", None), "message": str(exc)}
            probes.append({**item, "proxy_path": str(proxy_target), "status": status, "error": error,
                "operation_scope": "equal-length separate owned storage probe; not real output or a full CLI continuation"})
    # Also call the actual atomic writer on the intended maximum committed
    # manifest path, so source temp naming/flush/replace participate directly.
    direct_atomic = []
    relative = attempt / "upstream/transport_checkpoints" / f"00001554-{sha24}" / "manifest.json"
    for index, (variant, output) in enumerate(variants.items()):
        prefix = probe_root / f"v{index}"
        proxy = prefix / ("p" * (len(str(output)) - len(str(prefix)) - 1))
        try:
            atomic(proxy.joinpath(*relative.parts), {"fixture_only": True, "scope": "exact captured atomic_json"})
            status, error = "passed", None
        except OSError as exc:
            status, error = "failed", {"type": type(exc).__name__, "errno": exc.errno, "winerror": getattr(exc, "winerror", None), "message": str(exc)}
        direct_atomic.append({"variant": variant, "status": status, "error": error, "real_pid_digits": len(str(os.getpid()))})
    summaries = []
    for variant in variants:
        current = [row for row in rows if row["variant"] == variant and row["current_implementation_path"]]
        summaries.append({"variant": variant, "current_path_max_characters": max(row["characters"] for row in current),
            "largest_categories": [row["category"] for row in current if row["characters"] == max(item["characters"] for item in current)],
            "failed_storage_probes": [row["category"] for row in probes if row["variant"] == variant and row["status"] == "failed"],
            "historical_nested_copy_characters": next(row["characters"] for row in rows if row["variant"] == variant and not row["current_implementation_path"])})
    write(OUT / "result.json", {"kind": "source_based_windows_path_and_actual_isolated_storage_audit", "source_manifest_sha256": sha(OUT / "source-manifest.json"),
        "registered_unit_longest": unit, "platform": os.name, "model_calls": 0,
        "planned_outputs_touched": False, "full_cli_resume_executed": False,
        "assumptions": {"maximum_pid_digits": 10, "stage_time_ns_digits": 19, "ordinal_digits": 8,
            "attempt_digits": 4, "scope": "Current777 request/CPU resource configuration and fixed task identifiers; arbitrary future task IDs, future epoch lengths and many new study copies need their own audit."},
        "summaries": summaries, "calculated_paths": rows, "equal_length_actual_storage_probes": probes,
        "captured_atomic_json_manifest_probes": direct_atomic,
        "limitations": ["Storage probes use synthetic bytes and equal-length separate paths, not actual baseline outputs.",
            "Python file I/O does not verify Codex process command-line/output handling.", "This does not establish complete CLI resume correctness under the planned release directory.",
            "MAX_PATH behavior depends on OS/runtime/application long-path support. Observed failures are local evidence, not a universal Windows limit."]})
    print(json.dumps({"result": str(OUT / "result.json"), "summaries": summaries, "full_cli_resume_executed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
