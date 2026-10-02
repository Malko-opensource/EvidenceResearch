"""Bounded, provider-free fixtures of audited resume replay semantics.

Only this sidecar writes files. Captured source definitions are compiled without
imports or module bodies; provider.complete is always a local fixture. No solver
tool, CPU experiment, actual model, registration, or running process is used.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re
from abc import abstractmethod
from copy import copy
from collections import deque

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FUTURE = ROOT / "work/next-version/evidence_research"
UPSTREAM = ROOT / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27"
PINNED_SOURCE_SHA256 = {
    "future-arms.py": "c91f5e61b90feb119d002e2143f1b6cc3664462010a20124ff8ddbdfc344330f",
    "future-model.py": "21a4b73168428ad4795db55d6c95c2d7f3f2e7c44e0d9bc80fbc9e6a5e8a8131",
    "future-baseline.py": "a604076ea838e299991fb375709ca0741d785a2fc442f1abc81e96a47e1c27a4",
    "upstream-mlesolver.py": "cc110f2b07642532cca11bd8cbf74becfc41016c7f876c16f6d40379ec59882c",
    "upstream-agents.py": "d8d1eda040eb1fa897d84596a1b36f277e83da75433c1a9ac2d9efe5be5c749a",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def capture(name, path):
    target = OUT / "source" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        if not path.exists():
            raise RuntimeError(f"Required historical source snapshot is missing: {target}")
        target.write_bytes(path.read_bytes())
    if sha(target) != PINNED_SOURCE_SHA256[name]:
        raise ValueError(f"Historical source snapshot changed: {target}")
    return target, {"original_path": str(path), "captured_source": str(target), "sha256": sha(target)}


def definition(source, name):
    return next(node for node in ast.parse(source.read_text(encoding="utf-8")).body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign)) and
                (getattr(node, "name", None) == name or
                 isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)))


def execute(nodes, namespace, filename):
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(filename), "exec"), namespace)


class DiagnosticStop(RuntimeError):
    """Finite fixture boundary; no live research stopping rule is introduced."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-only", action="store_true",
                        help="Use only pinned audit snapshots; do not inspect any live or ignored source tree")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    live_paths = [FUTURE / n for n in ("arms.py", "model.py", "baseline.py")]
    live_paths += [ROOT / "evidence_research" / n for n in ("arms.py", "model.py", "baseline.py")]
    # A public clone need not contain the ignored work/next-version tree. The
    # captured, SHA-pinned sources above are sufficient for this historical proof.
    live_paths = [path for path in live_paths if path.exists()]
    if args.snapshot_only:
        live_paths = []
    live_before = {str(p): sha(p) for p in live_paths}
    sources = {}
    for name, path in (("future-arms.py", FUTURE / "arms.py"), ("future-model.py", FUTURE / "model.py"),
                       ("future-baseline.py", FUTURE / "baseline.py"), ("upstream-mlesolver.py", UPSTREAM / "mlesolver.py"),
                       ("upstream-agents.py", UPSTREAM / "agents.py")):
        captured, receipt = capture(name, path)
        sources[name] = (captured, receipt)
    arms = sources["future-arms.py"][0]
    model = sources["future-model.py"][0]
    mle = sources["upstream-mlesolver.py"][0]
    agents = sources["upstream-agents.py"][0]
    namespace = {"Path": Path, "json": json, "hashlib": hashlib,
                 "sha256_file": sha, "write_json": write}
    provider_definition = definition(model, "CodexProvider")
    provider_definition.body = [node for node in provider_definition.body
                                if isinstance(node, ast.FunctionDef) and node.name in {"_check_files", "_record_link"}]
    execute([definition(model, "ModelUnavailable"), definition(model, "PreregisteredResourcesExhausted"),
             provider_definition, definition(arms, "TOOL_CONTRACT"), definition(arms, "UpstreamCodexBridge")], namespace, arms)
    Bridge = namespace["UpstreamCodexBridge"]
    Exhausted = namespace["PreregisteredResourcesExhausted"]
    contract = namespace["TOOL_CONTRACT"]

    def request(prompt, system):
        return "UPSTREAM SYSTEM PROMPT:\n" + system + "\n\nUPSTREAM USER PROMPT:\n" + prompt + "\n\nSHARED HOST EXECUTION CONTRACT:\n" + contract

    class FixtureProvider:
        model = "fixture-provider-never-an-actual-model"

        def __init__(self, directory, response):
            self.evidence_dir = directory
            self.calls = []
            self.response = response
            self.last_evidence = {"classification": "synthetic_fixture_only", "execution_kind": "fixture"}

        def complete(self, prompt, *, call_id, json_response=False):
            self.calls.append({"prompt": prompt, "call_id": call_id})
            return self.response

    # Retain the original solver, command matching, rejection and full prompt.
    # The unsupported command never reaches an execution tool. Only the upstream
    # remove_figures filesystem side effect is replaced by a no-op fixture.
    solver_namespace = {"copy": copy, "abstractmethod": abstractmethod, "remove_figures": lambda: None}
    execute([definition(mle, name) for name in ("Command", "Replace", "Edit", "MLESolver")], solver_namespace, mle)
    Solver = solver_namespace["MLESolver"]

    def solver():
        obj = Solver(dataset_code="", notes=[], max_steps=3, insights="", plan="fixture plan", llm_str=FixtureProvider.model)
        # Identical state to original initial_solve immediately before gen_initial_code.
        obj.commands = [solver_namespace["Replace"]()]
        obj.model = FixtureProvider.model
        obj.supress_print = True
        return obj

    invalid = "unsupported_fixture_command_without_a_protocol_fence"
    warmup = []

    def capture_query(**kwargs):
        if len(warmup) == 12:
            raise DiagnosticStop("12 logical fixture requests observed")
        warmup.append(kwargs)
        return invalid

    solver_namespace["query_model"] = capture_query
    try:
        solver().gen_initial_code()
    except DiagnosticStop:
        pass
    warmup_sha = [hashlib.sha256(request(item["prompt"], item["system_prompt"]).encode()).hexdigest() for item in warmup]
    assert len(set(warmup_sha)) == 5 and len(set(warmup_sha[4:])) == 1
    provider = FixtureProvider(OUT / "fixtures/initializer/model", invalid)
    bridge = Bridge(provider, OUT / "fixtures/initializer", max_model_calls=777)
    bridge.prior_attempts = 777
    for item in warmup:
        bridge.replay[hashlib.sha256(request(item["prompt"], item["system_prompt"]).encode()).hexdigest()] = {
            "response": invalid, "evidence_dir": "synthetic-prior-response-never-real",
            "model_evidence": {"classification": "synthetic_fixture_only"}}

    def replay_query(**kwargs):
        if len(bridge.calls) == 12:
            raise DiagnosticStop("Stopped by local fixture observer, not model-call budget")
        return bridge(**kwargs)

    solver_namespace["query_model"] = replay_query
    try:
        solver().gen_initial_code()
    except DiagnosticStop:
        pass
    assert len(bridge.calls) == 12 and not provider.calls
    assert all(call["reused_completed_evidence"] and call["status"] == "completed" for call in bridge.calls)
    assert len(bridge.replay) == 5
    # With unchanged prompt and non-consuming lookup, another invocation remains
    # available at an already exhausted budget. We do not run an infinite loop.
    last = warmup[-1]
    bridge(**last)
    assert len(bridge.calls) == 13 and not provider.calls

    # Baseline contrast: absent prior replay, repeated identical logical requests
    # call the fixture provider independently and eventually honor the budget.
    fresh_provider = FixtureProvider(OUT / "fixtures/fresh/model", "fresh fixture")
    fresh = Bridge(fresh_provider, OUT / "fixtures/fresh", max_model_calls=2)
    fresh(FixtureProvider.model, "same", "same system")
    fresh(FixtureProvider.model, "same", "same system")
    try:
        fresh(FixtureProvider.model, "same", "same system")
        raise AssertionError("Fresh request budget should be enforced")
    except Exhausted:
        pass
    assert len(fresh_provider.calls) == 2

    # Proposed-remedy semantics only: a sidecar mapping consumes each prior
    # completion once. The live bridge class and package remain unchanged.
    class OneUseQueue:
        def __init__(self, items):
            self.items = {key: deque(values) for key, values in items.items()}

        def get(self, key):
            queue = self.items.get(key)
            return queue.popleft() if queue else None

    remedy_provider = FixtureProvider(OUT / "fixtures/one-use-prototype/model", invalid)
    remedy = Bridge(remedy_provider, OUT / "fixtures/one-use-prototype", max_model_calls=8)
    remedy.prior_attempts = 5
    remedy.replay = OneUseQueue({key: [value] for key, value in bridge.replay.items()})
    solver_namespace["query_model"] = remedy
    try:
        solver().gen_initial_code()
        raise AssertionError("An unsupported command must not yield a successful score")
    except Exhausted:
        pass
    assert len(remedy.calls) == 8 and len(remedy_provider.calls) == 3
    assert sum(call["reused_completed_evidence"] for call in remedy.calls) == 5

    # Inspect the actual three reviewer prompts, without using a model. Return a
    # structurally valid fixture review to keep original scoring control flow.
    reviewer_namespace = {"json": json, "re": re}
    execute([definition(agents, "extract_json_between_markers"), definition(agents, "get_score"),
             definition(agents, "ReviewersAgent")], reviewer_namespace, agents)
    review_response = "```json\n" + json.dumps({name: 3 for name in
        ("Overall", "Soundness", "Confidence", "Contribution", "Presentation", "Clarity", "Originality", "Quality", "Significance")}) + "\n```"
    reviewer_requests = []

    def record_review(**kwargs):
        reviewer_requests.append(kwargs)
        return review_response

    reviewer_namespace["query_model"] = record_review
    reviewer_namespace["ReviewersAgent"](model=FixtureProvider.model).inference("fixture plan", "fixture report")
    reviewer_sha = [hashlib.sha256(request(item["prompt"], item["system_prompt"]).encode()).hexdigest() for item in reviewer_requests]
    assert len(reviewer_sha) == len(set(reviewer_sha)) == 3
    repeated_reviewer_provider = FixtureProvider(OUT / "fixtures/reviewer/model", review_response)
    repeated_reviewer = Bridge(repeated_reviewer_provider, OUT / "fixtures/reviewer", max_model_calls=1)
    repeated_reviewer.prior_attempts = 1
    repeated_reviewer.replay[reviewer_sha[0]] = {"response": review_response,
        "evidence_dir": "synthetic-single-reviewer-response", "model_evidence": {"classification": "synthetic_fixture_only"}}
    reviewer_namespace["query_model"] = repeated_reviewer
    for _ in range(3):
        reviewer_namespace["get_score"]("fixture plan", "fixture report", FixtureProvider.model,
            reviewer_type="You are a harsh but fair reviewer and expect good experiments that lead to insights for the research topic.")
    assert len(repeated_reviewer.calls) == 3 and not repeated_reviewer_provider.calls

    live_after = {str(p): sha(p) for p in live_paths}
    assert live_before == live_after, "An audited live source changed during this replay; preserve snapshots and rerun after coordination"
    result = {"kind": "provider_free_resume_replay_independent_audit", "actual_model_calls": 0,
        "actual_cpu_experiments": 0, "fixture_scope": "Synthetic fixture completions are never measured research results. The finite observer boundary only makes the demonstration safe.",
        "source_evidence": {name: receipt for name, (_, receipt) in sources.items()},
        "live_source_before_after_identical": True,
        "live_source_integrity_check_paths": [str(path) for path in live_paths],
        "snapshot_only": args.snapshot_only,
        "original_initializer": {"bounded_logical_requests": len(warmup), "unique_prompt_hashes": len(set(warmup_sha)),
            "prompt_hashes": warmup_sha, "stable_from_zero_based_index": 4,
            "actual_retained_error_history_length": 4,
            "replayed_logical_requests": len(bridge.calls), "fresh_provider_fixture_calls": len(provider.calls),
            "prior_attempts_equal_budget": bridge.prior_attempts == bridge.max_model_calls,
            "cache_entries_before_and_after": 5, "stable_failure_return": "Command not supported, choose from existing commands",
            "original_command_matching_and_rejection_executed": True,
            "finding": "Original while True has no successful score; the stable cached prompt always remains available and the model budget never interrupts it."},
        "fresh_duplicate_prompt": {"fresh_provider_fixture_calls": len(fresh_provider.calls), "budget_exhaustion_after_fresh_calls": True},
        "one_use_queue_prototype_only": {"prior_actual_attempts_fixture": 5, "shared_request_budget_fixture": 8,
            "prior_completions_consumed_once": 5, "new_provider_fixture_requests": len(remedy_provider.calls),
            "budget_exhaustion_observed": True, "live_implementation_changed": False,
            "scope": "Demonstrates proposed within-invocation queue behavior only; checkpoint/logical identity durability is not implemented by this fixture."},
        "original_three_reviewers": {"logical_calls": len(reviewer_requests), "unique_full_prompt_hashes": len(set(reviewer_sha)),
            "prompt_hashes": reviewer_sha, "finding": "Reviewer-specific instructions differ. The original three reviewers do not collapse to one cache entry."},
        "same_reviewer_repeated_logical_requests": {"logical_calls": len(repeated_reviewer.calls),
            "unique_evidence_sources": len({call["evidence_dir"] for call in repeated_reviewer.calls}),
            "fresh_provider_fixture_calls": len(repeated_reviewer_provider.calls),
            "finding": "Repeated same-reviewer logical calls reuse one prior completion, so distinct sampling opportunities collapse."},
        "read_only_guarantee_scope": "Only sidecar source snapshots, fixtures, and this result were written. No live source, registration, current study, process, actual provider or fitting runner was modified or invoked."}
    # Preserve the original audit finding and fixture version. Portable reruns
    # produce a separate receipt while proving the same captured code behavior.
    result["historical_finding"] = {"path": str(OUT / "finding.json"), "sha256": sha(OUT / "finding.json")}
    result["original_fixture"] = {"path": str(OUT / "source/reproduce-at-audit.py"), "sha256": sha(OUT / "source/reproduce-at-audit.py")}
    result["reproduction_dependency"] = "SHA-pinned public source snapshots only; ignored next-version directory is optional"
    write(OUT / "portable-replay.json", result)
    print(json.dumps({"finding": str(OUT / "portable-replay.json"), "actual_model_calls": 0,
        "actual_cpu_experiments": 0, "stable_prompt": True, "unbounded_cache_reuse": True,
        "original_three_reviewer_prompts_unique": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
