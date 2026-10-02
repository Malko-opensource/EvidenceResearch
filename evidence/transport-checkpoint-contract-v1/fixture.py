"""Provider-free executable specification, not an acceptance test of future code.

Only reviewer-owned fixture files are written. Original save_state AST is invoked
through a class wrapper. Logical transcript cases define the required resume
semantics without changing main, next-version, registrations or active studies.
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os
import pickle
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "references/upstream/AgentLaboratory-d9017d90e329112d2a80b7712f37ee9094d2cd27/ai_lab_repo.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class ReconcileRequired(RuntimeError):
    pass


class FixtureWorkflow:
    def __init__(self):
        self.paper_index = 0
        self.phase_status = {"fixture_phase": False}
        self.last_response = None


class InvocationContract:
    """Ordered logical-tail replay is distinct from new same-prompt requests."""
    def __init__(self, checkpoint_cursor, history, fresh_values):
        self.cursor = checkpoint_cursor
        self.history = history
        self.fresh_values = iter(fresh_values)
        self.fresh_calls = 0
        self.replayed = []

    def call(self, prompt, phase="fixture_phase", role="fixture_role"):
        ordinal = self.cursor + 1
        identity = {"logical_ordinal": ordinal, "phase": phase, "role": role, "request_sha256": digest(prompt)}
        existing = [row for row in self.history if row["logical_ordinal"] == ordinal]
        if existing:
            if len(existing) != 1 or any(existing[0][key] != value for key, value in identity.items()):
                raise ReconcileRequired("The ordered tail differs; do not search another same-prompt receipt or make a fresh model attempt")
            row = existing[0]
            if row["status"] != "completed":
                raise ReconcileRequired("Unknown execution cannot be guessed or automatically repeated")
            self.replayed.append(ordinal)
        else:
            self.fresh_calls += 1
            row = {**identity, "status": "completed", "response": next(self.fresh_values),
                   "classification": "fixture_only_never_an_actual_model"}
            self.history.append(row)
        self.cursor = ordinal
        return row["response"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ORIGINAL.read_text(encoding="utf-8")
    workflow = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == "LaboratoryWorkflow")
    original_save = next(node for node in workflow.body if isinstance(node, ast.FunctionDef) and node.name == "save_state")
    ast_before = digest(ast.dump(original_save, include_attributes=False))
    namespace = {"pickle": pickle}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[original_save], type_ignores=[])), str(ORIGINAL), "exec"), namespace)
    pinned_save = namespace["save_state"]
    working = OUT / "working"
    (working / "state_saves").mkdir(parents=True, exist_ok=True)
    (OUT / "checkpoints").mkdir(exist_ok=True)
    transport = None
    checkpoints = []

    def wrapped_save_state(self, phase):
        # Class-level wrapper does not add closures/bridges to the pickled instance.
        pinned_save(self, phase)
        original_blob = working / f"state_saves/Paper{self.paper_index}.pkl"
        blob_sha = sha(original_blob)
        snapshot = OUT / "checkpoints" / f"{blob_sha}.pkl"
        if snapshot.exists():
            assert sha(snapshot) == blob_sha
        else:
            shutil.copy2(original_blob, snapshot)
        receipt = {"kind": "fixture_checkpoint_cursor_contract", "checkpoint_sha256": blob_sha,
                   "checkpoint_path": str(snapshot), "transport_cursor": transport.cursor,
                   "phase_status": self.phase_status, "original_save_state_ast_sha256": ast_before,
                   "classification": "fixture_only_not_a_real_baseline_checkpoint"}
        temporary = OUT / "checkpoint-receipt.tmp"
        temporary.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, OUT / "checkpoint-receipt.json")
        checkpoints.append(copy.deepcopy(receipt))

    FixtureWorkflow.save_state = wrapped_save_state
    original_cwd = Path.cwd()
    try:
        os.chdir(working)
        lab = FixtureWorkflow()
        history = []
        transport = InvocationContract(0, history, ["fresh A"])
        lab.last_response = transport.call("identical prompt P")
        lab.phase_status["fixture_phase"] = True
        lab.save_state("fixture_phase")
        checkpoint = checkpoints[-1]
        assert checkpoint["transport_cursor"] == 1
        assert not any("transport" in key or "bridge" in key for key in vars(lab))

        def restore():
            assert sha(checkpoint["checkpoint_path"]) == checkpoint["checkpoint_sha256"]
            # Own fixture file only, never an arbitrary external checkpoint.
            with Path(checkpoint["checkpoint_path"]).open("rb") as stream:
                return pickle.load(stream)

        # Prefix already embodied in the checkpoint must not be reused by the
        # next new logical request, even though its prompt is exactly the same.
        restored = restore()
        transport = InvocationContract(checkpoint["transport_cursor"], history, ["fresh B"])
        restored.last_response = transport.call("identical prompt P")
        assert restored.last_response == "fresh B" and transport.fresh_calls == 1 and not transport.replayed
        assert len(history) == 2 and history[0]["request_sha256"] == history[1]["request_sha256"]
        prefix_case = {"checkpoint_cursor": 1, "new_logical_ordinal": 2,
                       "same_prompt": True, "returned": restored.last_response,
                       "fresh_provider_fixture_calls": transport.fresh_calls, "prior_prefix_replayed": False}

        # Interrupted before checkpoint commit: restoring the stale cursor must
        # recover completion 2 from the ordered tail, then ordinal 3 is fresh.
        restored_again = restore()
        transport = InvocationContract(1, history, ["fresh C"])
        restored_again.last_response = transport.call("identical prompt P")
        assert restored_again.last_response == "fresh B" and transport.fresh_calls == 0 and transport.replayed == [2]
        restored_again.last_response = transport.call("identical prompt P")
        assert restored_again.last_response == "fresh C" and transport.fresh_calls == 1 and transport.replayed == [2]
        stale_case = {"checkpoint_cursor": 1, "tail_completion_replayed": [2], "then_new_logical_ordinal": 3,
                      "fresh_provider_fixture_calls": transport.fresh_calls, "same_prompt_completion_multiplicity_preserved": len(history)}

        # Reconstruct the same stale state again. Globally excluding 'consumed'
        # completions would wrongly make this request fresh; replay is necessary.
        reconstruction = InvocationContract(1, history, [])
        assert reconstruction.call("identical prompt P") == "fresh B"
        assert reconstruction.fresh_calls == 0 and reconstruction.replayed == [2]
        repeated_reconstruction = {"checkpoint_cursor": 1, "replayed_again_in_new_invocation": [2],
                                   "fresh_provider_fixture_calls": reconstruction.fresh_calls,
                                   "scope": "The same logical reconstruction reuses its original completion; fresh logical ordinals remain independent."}

        # Source tail roles/phase/prompt must match. Searching only by prompt
        # would silently assign another role's evidence to the wrong invocation.
        mismatch = InvocationContract(1, history, ["must never be consumed"])
        try:
            mismatch.call("identical prompt P", role="another_role")
            raise AssertionError("Role mismatch must fail closed")
        except ReconcileRequired:
            pass
        assert mismatch.fresh_calls == 0 and mismatch.cursor == 1
        initial = InvocationContract(0, history, [])
        assert initial.call("identical prompt P") == "fresh A"
        assert initial.call("identical prompt P") == "fresh B"
        assert initial.call("identical prompt P") == "fresh C"
        assert initial.fresh_calls == 0 and initial.replayed == [1, 2, 3]
    finally:
        os.chdir(original_cwd)
    ast_after = digest(ast.dump(original_save, include_attributes=False))
    assert ast_before == ast_after
    result = {"kind": "executable_transport_checkpoint_specification", "implementation_status": "proposal_fixture_only_not_validation_of_next_version",
              "actual_model_calls": 0, "actual_cpu_experiments": 0,
              "original_source": {"path": str(ORIGINAL), "sha256": sha(ORIGINAL), "save_state_ast_sha256": ast_before},
              "original_save_state_ast_unchanged": True, "class_level_wrapper_original_method_called": True,
              "checkpoint_receipt": checkpoint,
              "checkpoint_prefix_followed_by_same_prompt": prefix_case,
              "stale_checkpoint_tail_reconstruction": stale_case,
              "repeated_stale_checkpoint_reconstruction": repeated_reconstruction,
              "phase_role_request_mismatch_fails_closed_without_provider": True,
              "initial_state_reconstructs_all_original_completions_in_order": [1, 2, 3],
              "logical_history": history,
              "remaining_implementation_requirements": ["durable fsync and atomic checkpoint bundle commit", "unknown and definitive failed attempt handling", "original CPU tool-response replay and cursor", "request/role/cursor raw receipt auditing", "actual next-version implementation fixture verification"]}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": str(OUT / "result.json"), "kind": result["implementation_status"],
                      "prefix_same_prompt_fresh": True, "stale_checkpoint_tail_replay": True,
                      "actual_model_calls": 0, "actual_cpu_experiments": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
