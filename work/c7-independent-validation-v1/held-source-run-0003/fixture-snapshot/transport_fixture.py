"""Independent original-boundary fixture builder, not an actual research arm.

Provider files are fabricated, visibly fixture_only, and never adopted as real
model evidence. Optional CPU receipts use the trusted fixed runner over explicit
tiny public arrays; no sampler, private definitions, owner or test rows exist.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(compact(value)).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")


def link(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def public_bundle(task_version):
    task_id, seed = "fixture-only-public-arrays", 257
    train = [{"id": f"toy:train:{i}", "x": x, "y": 0.2 + 0.5*x + 0.7*x*x}
             for i, x in enumerate((-1.2, -0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9, 1.2))]
    validation = [{"id": f"toy:validation:{i}", "x": x, "y": 0.2 + 0.5*x + 0.7*x*x + 0.02}
                  for i, x in enumerate((-1.05, -0.75, -0.45, -0.15, 0.15, 0.45, 0.75, 1.05))]
    manifest = {"task_id": task_id, "seed": seed, "task_version": task_version,
        "generation": "Explicit small synthetic component arrays; no sampler, owner or test data.",
        "splits": {name: {"count": len(rows), "sha256": digest(rows),
                         "ids_sha256": digest([row["id"] for row in rows])}
                   for name, rows in (("train", train), ("validation", validation), ("test", []))}}
    return {"train": train, "validation": validation, "split_manifest": manifest}


class BoundaryFixture:
    def __init__(self, root, arm, *, failed_second=False, with_cpu=True, task_id_override=None,
                 include_all_returns=False, paths_only=False, selected_plan=None, replay_prefix=False):
        from evidence_research.context_boundary import ContextBoundaryRecorder
        from evidence_research.model import CodexProvider
        from evidence_research.tasks import TASK_VERSION, make_spec, run_task
        import evidence_research.context_boundary as context_module

        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.arm, self.boundaries, self.transport, self.runs, self.returned = arm, [], [], [], []
        self.folders, self.cpu_component_executions = [], 0
        self.envelope = {"reasoning_effort": "medium", "proposal_calls_per_unit": 10, "actual_cpu_executions_per_unit": 10}
        self.bundle = public_bundle(TASK_VERSION)
        self.public = {"task_id": self.bundle["split_manifest"]["task_id"], "seed": 257,
                       "task_bundle": self.bundle, "objective": "Explicit synthetic component fixture only; no research trial."}
        if task_id_override is not None:
            self.public["task_id"] = task_id_override
        self.model = "fixture-model"
        source_root = Path(context_module.__file__).resolve().parent
        implementation = source_root / ("arms.py" if arm == "B" else "comparison_arms.py")
        self.registration = self.root / "callback-registration.json"
        write(self.registration, {"model_id": self.model, "public_task": self.public,
            "resource_envelope": self.envelope, "implementation_sha256": sha(implementation),
            "fixture_only": True, "actual_provider_calls": 0, "research_trial": False})
        self.recorder = ContextBoundaryRecorder(self.root, arm=arm, registration=self.registration,
            model_id=self.model, resource_envelope=self.envelope, public_task=self.public, fixture_only=True)
        self.transport_path = self.root / "model-transport.jsonl"
        provider = SimpleNamespace(model=self.model, reasoning_effort="medium", evidence_dir=self.root / "model")
        for ordinal in range(3):
            call = f"{'upstream' if arm == 'B' else 'improved'}-{ordinal:04d}"
            logical = {"ordinal": ordinal, "host_ordinal": ordinal*2,
                       "phase": "report writing" if ordinal == 2 else "running experiments",
                       "role": {"kind": "fixture-planner-or-report-author"}}
            if ordinal == 2 and replay_prefix:
                self.recorder.record_model(folder=self.folders[0],logical_context={**logical,"role":{"kind":"fixture-reconstruction"}},
                    boundary=self.boundaries[0],replay=True)
            if ordinal == 2 and selected_plan is not None:
                self.recorder.capture_report_era(logical_context=logical,selected_output="\n".join(self.returned),
                    selected_code="trusted fixed component only",phase="report writing",selected_plan=selected_plan)
            if arm == "C":
                memory = [{"run_id": row["folder"].name, "metrics": row["result"]["metrics"]} for row in self.runs]
                if paths_only: memory = [{"run_id":row["folder"].name,"result_path":str(row["folder"] / "result.json")} for row in self.runs]
                prompt_object={"public_task": self.public, "verified_memory": memory,
                    "goal": {"objective": "Plan a fixture only."}, "instructions": "Propose a future comparison; do not assert a measured improvement."}
                if ordinal == 2 and selected_plan is not None: prompt_object["original_selected_native_plan"]=selected_plan
                prompt = json.dumps(prompt_object,ensure_ascii=False,sort_keys=True)
            else:
                host_text = "\n".join(self.returned) if include_all_returns else self.returned[-1] if self.returned else "No previous fixture experiment."
                if paths_only: host_text = "\n".join(str(row["folder"] / "result.json") for row in self.runs)
                prompt = ("UPSTREAM SYSTEM PROMPT:\nSynthetic original report-role fixture.\n\nUPSTREAM USER PROMPT:\n"
                          + host_text + "\n\nSHARED HOST EXECUTION CONTRACT:\nSynthetic allowlisted component contract only.")
                if ordinal == 2 and selected_plan is not None: prompt += "\nOriginal selected native plan: "+selected_plan
            full_prompt = CodexProvider.guard + prompt
            boundary = self.recorder.capture(call_id=call, prompt=prompt, full_prompt=full_prompt,
                logical_context=logical, transport_path=self.transport_path, provider=provider)
            self.boundaries.append(boundary)
            self.transport.append({"call_id": call, "status": "requested", "context_boundary": boundary,
                                   "logical_request": logical, "fixture_only": True})
            folder = provider.evidence_dir / call; folder.mkdir(parents=True)
            request = {"model": self.model, "prompt": prompt, "full_prompt": full_prompt,
                "reasoning_effort": "medium", "provider_source_sha256": sha(source_root / "model.py"),
                "execution_kind": "real_model", "fixture_only": True}
            request["fingerprint"] = digest({key: request[key] for key in
                ("model", "prompt", "reasoning_effort", "full_prompt", "provider_source_sha256")})
            request["command"] = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                "--sandbox", "read-only", "--model", self.model, "--cd", str(self.root / "public_model_cwd"),
                "--json", "-c", 'approval_policy="never"', "--output-last-message", str(folder / "response.txt"),
                "-c", 'model_reasoning_effort="medium"', "-"]
            write(folder / "request.json", request)
            failed = failed_second and ordinal == 1
            usage = {} if failed else {"input_tokens": 10*(ordinal+1), "output_tokens": 2*(ordinal+1)}
            event = {"type": "turn.failed", "error": {"message": "Synthetic definitive no-action failure; no provider invoked."}} if failed else {"type": "turn.completed", "usage": usage}
            (folder / "events.jsonl").write_text(json.dumps(event)+"\n", encoding="utf-8")
            (folder / "stderr.log").write_text("Fabricated transport format. Actual provider calls=0.\n", encoding="utf-8")
            if not failed:
                (folder / "response.txt").write_text("Synthetic response; not a real model observation.\n", encoding="utf-8")
            result = {"model": self.model, "status": "failed" if failed else "completed", "execution_kind": "real_model",
                "fingerprint": request["fingerprint"], "returncode": 1 if failed else 0, "wall_seconds": 1.25,
                "usage": usage, "tool_calls": [], "fixture_only": True,
                "files": {path.name: sha(path) for path in folder.iterdir()}}
            write(folder / "result.json", result)
            self.folders.append(folder)
            self.recorder.record_model(folder=folder, logical_context=logical, boundary=boundary)
            self.transport.append({"call_id": call, "status": result["status"], "context_boundary": boundary,
                                   "logical_request": logical, "evidence_dir": str(folder), "fixture_only": True})
            if with_cpu and ordinal < 2 and not failed:
                directory = self.root / "research" / "runs" / f"cpu-{ordinal}"
                spec = make_spec(self.public["task_id"], self.public["seed"], {"degree": ordinal+1, "alpha": 0.1},
                    model=self.model, task_bundle=self.bundle, resource_envelope=self.envelope)
                spec["fixture_only"] = True
                actual_result = run_task(spec, directory)
                if actual_result["status"] != "success":
                    raise AssertionError("trusted CPU fixture itself failed: " + str(actual_result.get("error")))
                self.cpu_component_executions += 1
                self.runs.append({"folder": directory, "spec": spec, "result": actual_result})
                returned = json.dumps({"execution_id": directory.name, "metrics": actual_result["metrics"],
                    "kind": "trusted_cpu_component_fixture_not_research", "result_path": str(directory / "result.json"),
                    "result_sha256": sha(directory / "result.json")}, ensure_ascii=False, sort_keys=True)
                self.returned.append(returned)
                self.recorder.record_cpu_return(logical_context={**logical, "host_ordinal": ordinal*2+1},
                    returned_text=returned, records=[{"run_dir": str(directory)}])
            self.flush_transport()

    def flush_transport(self):
        self.transport_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n" for row in self.transport), encoding="utf-8")

    def target(self):
        return deepcopy(self.boundaries[-1])

    def raw_receipt_inventory(self):
        return [{"folder": str(folder), "files": {path.name: sha(path) for path in folder.iterdir() if path.is_file()},
                 "classification": "synthetic_provider_format_no_actual_model"} for folder in self.folders]
