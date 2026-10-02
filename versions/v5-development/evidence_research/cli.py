"""Executable, resumable evidence-oriented research CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .engine import Engine
from .model import CodexProvider, ModelUnavailable
from .proposer import ResearchProposer
from .store import Store, EvidenceError
from .tasks import DEVELOPMENT_TASKS, make_spec, run_task
from .verifier import verify


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("work/research"))
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor")
    p = subs.add_parser("init")
    p.add_argument("--goal", required=True)
    p.add_argument("--task", choices=DEVELOPMENT_TASKS, default="dev-quadratic")
    subs.add_parser("state")
    p = subs.add_parser("memory")
    p.add_argument("query", nargs="?", default="")
    subs.add_parser("integrity")
    p = subs.add_parser("run-spec")
    p.add_argument("spec", type=Path)
    subs.add_parser("resume")
    p = subs.add_parser("spec")
    p.add_argument("--task", choices=DEVELOPMENT_TASKS, default="dev-quadratic")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--degree", type=int, default=1)
    p.add_argument("--alpha", type=float, default=0)
    p.add_argument("--output", type=Path, required=True)
    p = subs.add_parser("research")
    p.add_argument("--task", choices=DEVELOPMENT_TASKS, default="dev-quadratic")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--model", default="gpt-6.1-sol")
    p.add_argument("--reasoning-effort", default=None)
    p.add_argument("--target-mse", type=float, required=True)
    p.add_argument("--baseline-run-id")
    p = subs.add_parser("model-smoke")
    p.add_argument("--model", default="gpt-6.1-sol")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            codex = shutil.which("codex")
            status = None
            if codex:
                completed = subprocess.run([codex, "login", "status"], capture_output=True,
                                           text=True, encoding="utf-8", errors="replace")
                status = {"logged_in": completed.returncode == 0,
                          "diagnostic": (completed.stdout + completed.stderr).strip()}
            emit({"python": sys.version, "codex": codex, "authentication": status,
                  "dependencies": "standard library only", "gpu_required": False,
                  "model_access": "established only by a real successful call"})
        elif args.command == "spec":
            spec = make_spec(args.task, args.seed, {"degree": args.degree, "alpha": args.alpha})
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            emit({"registered_proposal": str(args.output), "executed": False})
        elif args.command == "init":
            store = Store(args.workspace)
            store.init_goal({"objective": args.goal, "task_id": args.task,
                             "memory_query": args.task, "status": "active"})
            emit(store.state())
        elif args.command == "state":
            emit(Store(args.workspace).state())
        elif args.command == "memory":
            emit(Store(args.workspace).search(args.query))
        elif args.command == "integrity":
            result = Store(args.workspace).verify_integrity()
            emit(result)
            if not result["valid"]:
                return 1
        elif args.command == "run-spec":
            emit(Engine(args.workspace, run_task, verify).step(load(args.spec)))
        elif args.command == "resume":
            emit(Engine(args.workspace, run_task, verify).resume())
        elif args.command == "model-smoke":
            provider = CodexProvider(args.workspace / "model-calls", args.model)
            response = provider.complete('Return exactly {"status":"connected"}.',
                                         call_id="connectivity", json_response=True)
            emit({"response": response, "evidence": provider.last_evidence,
                  "scope": "connectivity only; not research performance"})
        elif args.command == "research":
            store = Store(args.workspace)
            if not store.state().get("goal"):
                store.init_goal({"objective": f"Reduce {args.task} validation MSE to {args.target_mse}",
                                 "task_id": args.task, "memory_query": args.task,
                                 "status": "active", "criterion": {"direction": "min", "threshold": args.target_mse}})
            else:
                previous = store.state()["goal"]
                if previous.get("task_id") != args.task or previous.get("criterion") != {"direction": "min", "threshold": args.target_mse}:
                    raise ValueError("Research goal/criterion mismatch; use a new workspace for changed goals")
            for prior in store.list_runs():
                registered = prior["spec"]
                verification = prior.get("verification") or {}
                if registered.get("task_id") == args.task and registered.get("seed") == args.seed and registered.get("model") == args.model:
                    value = verification.get("metrics", {}).get("validation_mse")
                    if verification.get("valid") and isinstance(value, (float, int)) and value <= args.target_mse:
                        if not store.verify_integrity()["valid"]:
                            raise ValueError("Prior evidence integrity failed")
                        emit({"development_objective_satisfied": True, "metric": value,
                              "evidence_run": prior["run_id"], "resumed_without_execution": True,
                              "overall_goal_complete": False})
                        return 0
            provider = CodexProvider(args.workspace / "model-calls", args.model,
                                     reasoning_effort=args.reasoning_effort)
            proposer = ResearchProposer(provider, args.task, args.seed,
                                        {"direction": "min", "threshold": args.target_mse},
                                        baseline_run_id=args.baseline_run_id)
            engine = Engine(args.workspace, run_task, verify, proposer)
            while True:
                result = engine.step()
                emit(result)
                if result.get("status") in ("needs_proposal", "unknown_execution") or result.get("blocked"):
                    return 2
                if result.get("resumed_without_execution"):
                    emit({"status": "needs_new_hypothesis", "reason": "Completed configuration returned; no repeated execution"})
                    return 2
                check = result.get("verification") or {}
                metric = check.get("metrics", {}).get("validation_mse")
                if check.get("valid") and isinstance(metric, (float, int)) and metric <= args.target_mse:
                    emit({"development_objective_satisfied": True, "metric": metric,
                          "evidence_run": result["run_id"], "overall_goal_complete": False,
                          "next": "Independent preregistered original B versus improved C evaluation"})
                    return 0
    except (ValueError, OSError, ModelUnavailable, EvidenceError) as error:
        emit({"status": "attention_required", "error_type": type(error).__name__,
              "reason": str(error), "goal_complete": False})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
