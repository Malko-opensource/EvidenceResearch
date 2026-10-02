"""Pinned, relocated replay of selected published development units.

Original receipts are never rewritten. This is a development evidence audit,
not a fresh model run, complete semantic report review or adoption decision.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import random
from pathlib import Path, PurePosixPath, PureWindowsPath


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def equal(a, b):
    return isinstance(a, (float, int)) and isinstance(b, (float, int)) and math.isfinite(a) and math.isfinite(b) and math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-9)


REGISTRATION_SHA256 = "a8fdd8c5500961350b289b8798a0ee9dde116ed2d07ee0ef13e131701ec0be92"
PUBLICATION_SHA256 = "b71986a181f3c8359ca14151ce746b3110c33131001b4c225ce977c419c5cfb2"


class Bundle:
    """Map recorded names to authenticated local bytes; never open original names."""
    def __init__(self, root, recorded_root):
        self.root = Path(root).resolve()
        self.path_class = PureWindowsPath if PureWindowsPath(recorded_root).drive else PurePosixPath
        self.recorded_root = self.path_class(recorded_root)
        require(self.recorded_root.is_absolute(), "Explicit absolute recorded root required")
        self.checked, self.trusted_sources, self.allowed = {}, {}, {}

    def resolve(self, recorded):
        original = self.path_class(recorded)
        require(not original.root or original.is_absolute(), "Rooted relative path refused")
        require(".." not in original.parts, "Parent traversal in evidence path")
        require(not original.drive or original.is_absolute(), "Drive-relative path refused")
        try:
            relative = original.relative_to(self.recorded_root) if original.is_absolute() else original
        except ValueError as error:
            raise ValueError("Recorded evidence lies outside the explicitly mapped original root") from error
        require(all(":" not in part for part in relative.parts), "Alternate stream path refused")
        actual = self.root.joinpath(*relative.parts)
        require(actual.resolve().is_relative_to(self.root), "Evidence escapes relocated bundle")
        require(not actual.is_symlink() and not any(p.is_symlink() for p in actual.parents if p.is_relative_to(self.root)), "Symlink evidence refused")
        return actual

    def allow(self, actual, expected):
        actual = Path(actual)
        require(actual.resolve().is_relative_to(self.root), "Hash target escapes bundle")
        key = actual.relative_to(self.root).as_posix()
        require(actual.name != "owner-request.json" and not actual.name.endswith("-owner.json"), "Private owner file may not be read")
        require(key not in self.allowed or self.allowed[key] == expected, "Conflicting external evidence anchors")
        require(isinstance(expected,str) and len(expected)==64 and all(c in "0123456789abcdef" for c in expected), "Invalid external SHA")
        self.allowed[key] = expected
        return self.check(actual, expected)

    def check(self, actual, expected=None):
        actual = Path(actual)
        require(actual.resolve().is_relative_to(self.root), "Hash target escapes bundle")
        key = actual.relative_to(self.root).as_posix()
        require(key in self.allowed and (expected is None or self.allowed[key] == expected), "Evidence lacks an external byte anchor")
        require(actual.is_file() and not actual.is_symlink(), "Missing or symlink evidence")
        require(not any(p.is_symlink() for p in actual.parents if p.is_relative_to(self.root)), "Symlink parent refused")
        require(sha(actual) == self.allowed[key], f"Original bytes changed: {key}")
        self.checked[key] = self.allowed[key]
        return actual

    def load(self, path):
        return load(self.check(path))

    def text(self, path):
        return self.check(path).read_text(encoding="utf-8")

    def link(self, record):
        return self.check(self.resolve(record["path"]), record["sha256"])


def function_nodes(tree, names):
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    require(len(selected)==len(names) and {node.name for node in selected}==set(names), "Pinned pure function inventory differs")
    return selected


def compiled_pure(nodes, namespace):
    # Source bytes are externally authenticated before this AST subset is used.
    # No candidate, full module, provider or runner is ever executed.
    module = ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0), *nodes],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),"externally-pinned-pure-reference-subset","exec"),namespace)
    return namespace


def owner_from_pinned_generation(bundle, study, registration, entry, public):
    paths={name:study / "source-snapshot/evidence_research" / name for name in ("tasks.py","store.py","study.py","evaluation.py")}
    trees={name:ast.parse(bundle.text(path)) for name,path in paths.items()}
    constants={}
    for node in trees["tasks.py"].body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ("TASK_VERSION","_TASK_DEFINITIONS"):
            constants[node.targets[0].id]=ast.literal_eval(node.value)
    require(set(constants)=={"TASK_VERSION","_TASK_DEFINITIONS"},"Pinned generation constants absent")
    namespace={"json":json,"hashlib":hashlib,"random":random,**constants}
    compiled_pure(function_nodes(trees["tasks.py"],("canonical_bytes","value_hash","task_data","split_manifest")),namespace)
    require(public["task_id"] in constants["_TASK_DEFINITIONS"],"Only original deterministic development tasks supported")
    config_unit=next(unit for unit in registration["config"]["units"] if unit["unit_id"]==entry["unit_id"])
    require(public["task_id"]==config_unit["task_id"] and public["seed"]==config_unit["seed"] and public["task_version"]==constants["TASK_VERSION"],"Registered generation conditions differ")
    data=namespace["task_data"](public["task_id"],public["seed"])
    manifest=namespace["split_manifest"](public["task_id"],public["seed"])
    require(public["task_bundle"]=={"train":data["train"],"validation":data["validation"],"split_manifest":manifest},"Pure generation does not reproduce original public bytes/manifest")
    shapes=[node.value for node in ast.walk(trees["study.py"]) if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="owner" and isinstance(node.value,ast.Dict)]
    require(len(shapes)==1,"Original registered owner-object shape ambiguous")
    require(set(ast.literal_eval(key) for key in shapes[0].keys)=={"unit_id","test","test_sha256","scope"},"Original owner shape differs")
    owner=eval(compile(ast.Expression(shapes[0]),"externally-pinned-owner-shape","eval"),{"identity":entry["unit_id"],"data":data,"value_hash":namespace["value_hash"]})
    serial_namespace=compiled_pure(function_nodes(trees["store.py"],("canonical_json",)),{"json":json})
    atomic=next(node for node in trees["store.py"].body if isinstance(node,ast.FunctionDef) and node.name=="atomic_json")
    serial=[node.value for node in atomic.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="data"]
    require(len(serial)==1,"Original serializer expression absent")
    owner_bytes=eval(compile(ast.Expression(serial[0]),"externally-pinned-owner-serializer","eval"),{"canonical_json":serial_namespace["canonical_json"],"value":owner})
    owner_bytes_sha=hashlib.sha256(owner_bytes).hexdigest()
    require(owner_bytes_sha==entry["owner_sha256"],"Regenerated original owner JSON serializer byte SHA differs")
    require(value_sha(owner["test"])==owner["test_sha256"]==manifest["splits"]["test"]["sha256"],"Regenerated owner test/value SHA differs")
    metric_namespace=compiled_pure(function_nodes(trees["evaluation.py"],("_owner_metric",)),{"math":math})
    proof={"kind":"in_memory_pinned_generation_with_original_serializer","unit_id":entry["unit_id"],"owner_json_sha256":owner_bytes_sha,
        "test_value_sha256":owner["test_sha256"],"test_ids_sha256":manifest["splits"]["test"]["ids_sha256"],
        "test_count":manifest["splits"]["test"]["count"],"source_sha256":{name:bundle.trusted_sources[name] for name in paths},
        "private_owner_file_opened":False,"test_rows_printed_or_persisted":False,"owner_request_opened":False}
    return owner,proof,metric_namespace["_owner_metric"]


def prepare_bundle(root,recorded_root,study_relative,registration_sha256,manifest_relative,manifest_sha256):
    require(registration_sha256==REGISTRATION_SHA256,"Unrecognized external study registration pin")
    require(manifest_sha256==PUBLICATION_SHA256,"Unrecognized human-approved publication manifest pin")
    bundle=Bundle(root,recorded_root);study=bundle.resolve(study_relative)
    registration=bundle.load(bundle.allow(study / "pilot-registration.json",registration_sha256))
    publication=bundle.load(bundle.allow(bundle.resolve(manifest_relative),manifest_sha256))
    require(publication["file_count"]==len(publication["files"]) and publication["owner_original_rows_included"] is False and publication["owner_requests_included"] is False,"Publication scope changed")
    seen=set()
    for record in publication["files"]:
        require(record["path"] not in seen,"Duplicate publication manifest entry")
        seen.add(record["path"])
        path=bundle.allow(bundle.resolve(record["path"]),record["sha256"])
        require(path.stat().st_size==record["bytes"],"Approved publication byte size differs")
    require(value_sha(registration["config"])==registration["config_sha256"],"Original registration config digest differs")
    for path,expected in registration["sources"].items():
        name=bundle.path_class(path).name
        require(name not in bundle.trusted_sources,"Ambiguous registered source filename")
        bundle.allow(study / "source-snapshot/evidence_research" / name,expected)
        bundle.trusted_sources[name]=expected
    model_tree=ast.parse(bundle.text(study / "source-snapshot/evidence_research/model.py"))
    provider=next(node for node in model_tree.body if isinstance(node,ast.ClassDef) and node.name=="CodexProvider")
    guards=[node.value for node in provider.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=="guard"]
    require(len(guards)==1,"Pinned proposal-only guard absent")
    bundle.provider_guard=ast.literal_eval(guards[0])
    return bundle,study,registration,publication


def replay_cpu(bundle, run):
    spec, result = bundle.load(run / "registered_spec.json"), bundle.load(run / "result.json")
    require(result["execution_kind"] == "actual_cpu_execution" and result["status"] == "success", "Completed actual CPU success required")
    require(value_sha(spec) == result["spec_sha256"], "Registered specification link changed")
    hashes = result["artifact_hashes"]
    required = {"registered_spec.json", "run.log", "source/evidence_research/__init__.py",
                "source/evidence_research/tasks.py", "source/evidence_research/verifier.py",
                "model.json", "predictions.json", "train.json", "validation.json", "split_manifest.json"}
    require(set(hashes) == required, "CPU artifact inventory changed")
    for name, expected in hashes.items():
        require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts, "Unsafe CPU artifact path")
        bundle.check(run / name, expected)
    require({bundle.resolve(path) for path in result["artifacts"]} == {run / name for name in required}, "CPU artifact path links changed")
    require(hashes["source/evidence_research/tasks.py"] == spec["implementation_sha256"] and hashes["source/evidence_research/verifier.py"] == spec["evaluator_sha256"], "Frozen CPU implementation or evaluator changed")
    require(all(hashes[f"source/evidence_research/{name}"] == bundle.trusted_sources.get(name)
                for name in ("tasks.py", "verifier.py")),
            "CPU fit/evaluator source differs from the externally pinned study registration")
    model = bundle.load(run / "model.json")
    require(model["config"] == spec["config"] and model["fit_split"] == "train", "CPU configuration or fit split changed")
    rows = {split: bundle.load(run / f"{split}.json") for split in ("train", "validation")}
    public = spec["task_bundle"]
    require(all(rows[s] == public[s] for s in rows), "Actual rows differ from registered public bundle")
    require(bundle.load(run / "split_manifest.json") == public["split_manifest"], "Registered split manifest changed")
    require(value_sha(public["split_manifest"]) == spec["split_manifest_sha256"], "Registered split digest changed")
    require(value_sha({k: v["sha256"] for k, v in public["split_manifest"]["splits"].items()}) == spec["data_sha256"], "Registered data digest changed")
    require(not (run / "test.json").exists(), "Hidden test materialized in CPU evidence")
    require(value_sha([r["id"] for r in rows["train"]]) == model["fit_ids_sha256"], "Fit observation IDs changed")
    ids = [set(r["id"] for r in rows[s]) for s in rows]
    require(all(len(ids[i]) == len(rows[s]) for i, s in enumerate(rows)) and not ids[0] & ids[1], "Duplicate or overlapping public observations")
    # Execute only the original, hash-checked independent reference-fit definition.
    # No generated candidate, model response or full archived module is executed.
    source = ast.parse(bundle.text(run / "source/evidence_research/verifier.py"))
    reference = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "_reference_fit"]
    require(len(reference) == 1, "Frozen independent fit definition missing")
    namespace = {"math": math}
    exec(compile(ast.Module(body=reference, type_ignores=[]), "hash-checked-independent-reference-fit", "exec"), namespace)
    config = spec["config"]
    weights = namespace["_reference_fit"](rows["train"], config["degree"], config["alpha"])
    require(len(weights) == len(model["weights"]) and all(equal(a, b) for a, b in zip(weights, model["weights"])), "Independent fit does not reproduce saved weights")
    predictions = bundle.load(run / "predictions.json")
    require(set(predictions) == set(rows), "Prediction split inventory changed")
    metrics = {}
    for split, observed in rows.items():
        saved = predictions[split]
        require(len(saved) == len(observed) and all(p["id"] == r["id"] for p, r in zip(saved, observed)), "Prediction observation IDs changed")
        calculated = [math.fsum(w * r["x"]**p for p, w in enumerate(weights)) for r in observed]
        require(all(equal(p["prediction"], v) for p, v in zip(saved, calculated)), "Independent predictions differ")
        metrics[split + "_mse"] = math.fsum((r["y"] - p["prediction"])**2 for r, p in zip(observed, saved)) / len(observed)
    require(set(metrics) == set(result["metrics"]) and all(equal(v, result["metrics"][k]) for k, v in metrics.items()), "Actual CPU metric mismatch")
    measured = {c["metric"]: c for c in result["claims"] if c["kind"] == "measured"}
    require(set(measured) == set(metrics), "Measured claim inventory mismatch")
    for name, claim in measured.items():
        require(equal(claim["value"], metrics[name]) and bundle.resolve(claim["artifact"]) == run / "predictions.json" and claim["sha256"] == hashes["predictions.json"], "Measured claim evidence mismatch")
    return metrics, model, rows, result["execution_seconds"]


def replay_model(bundle, folder, model_id, effort):
    record = bundle.load(folder / "result.json")
    for name, expected in record["files"].items():
        require(PurePosixPath(name).name == name, "Unsafe raw provider filename")
        bundle.check(folder / name, expected)
    require(set(record["files"]) == {"request.json", "events.jsonl", "response.txt", "stderr.log"}, "Provider file inventory changed")
    request = bundle.load(folder / "request.json")
    events = [json.loads(line) for line in bundle.text(folder / "events.jsonl").splitlines() if line.strip()]
    require(record["status"] == "completed" and record["execution_kind"] == "real_model" and record["returncode"] == 0, "Actual successful model completion required")
    require(record["model"] == model_id and request["model"] == model_id and request["reasoning_effort"] == effort, "Provider model or effort changed")
    require(request.get("provider_source_sha256")==bundle.trusted_sources["model.py"],"Provider differs from externally pinned source")
    require(request.get("full_prompt")==bundle.provider_guard+request["prompt"],"Original proposal-only input guard differs")
    identity={key:request[key] for key in ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")}
    require(request.get("fingerprint")==record.get("fingerprint")==value_sha(identity),"Raw provider request fingerprint differs")
    command=request.get("command")
    require(isinstance(command,list) and all(isinstance(value,str) for value in command) and len(command)>3 and command[1]=="exec" and command[-1]=="-","Provider command contract differs")
    flags,options,configs=set(),{},[]
    required_flags={"--ignore-user-config","--ephemeral","--skip-git-repo-check","--json"}
    index=2
    while index<len(command)-1:
        token=command[index]
        if token in required_flags:
            require(token not in flags,"Duplicate provider isolation flag")
            flags.add(token);index+=1
        elif token in ("--sandbox","--model","--cd","--output-last-message"):
            require(token not in options and index+1<len(command)-1,"Duplicate/missing provider option")
            options[token]=command[index+1];index+=2
        elif token=="-c":
            require(index+1<len(command)-1,"Missing provider configuration")
            configs.append(command[index+1]);index+=2
        else:raise ValueError("Unregistered provider command option")
    expected_configs=['approval_policy="never"']+([f'model_reasoning_effort="{effort}"'] if effort is not None else [])
    require(flags==required_flags and options.get("--sandbox")=="read-only" and options.get("--model")==model_id and sorted(configs)==sorted(expected_configs),"Model/isolation/effort settings differ")
    cwd=bundle.resolve(options["--cd"]);last=bundle.resolve(options["--output-last-message"])
    require(cwd.is_relative_to(bundle.arm_output) and cwd.name=="public_model_cwd" and last==folder / "response.txt","Provider public cwd or output boundary differs")
    require(isinstance(record["wall_seconds"],(int,float)) and not isinstance(record["wall_seconds"],bool) and math.isfinite(record["wall_seconds"]) and record["wall_seconds"]>=0,"Invalid model elapsed time")
    require(not record["tool_calls"], "Forbidden provider tool invocation")
    require(not any(e.get("item", {}).get("type") in ("command_execution", "mcp_tool_call", "web_search", "file_change") for e in events), "Raw provider tool invocation")
    complete = [e for e in events if e.get("type") == "turn.completed"]
    require(len(complete) == 1, "Exactly one raw completed turn required")
    usage = complete[0]["usage"]
    for key in ("input_tokens", "output_tokens"):
        require(isinstance(usage[key], int) and usage[key] >= 0 and usage[key] == record["usage"][key], "Raw provider usage mismatch")
    return usage["input_tokens"], usage["output_tokens"], record["wall_seconds"]


def replay_unit(bundle,study,registration,publication,unit_id):
    require(unit_id in publication["completed_development_units"],"Unit is outside this approved completed publication bundle")
    matching=[entry for entry in registration["units"] if entry["unit_id"]==unit_id]
    require(len(matching)==1,"Unique registered unit required")
    entry=matching[0]
    public=bundle.load(bundle.allow(bundle.resolve(entry["public_path"]),entry["public_sha256"]))
    owner,owner_proof,owner_metric=owner_from_pinned_generation(bundle,study,registration,entry,public)
    arms = {}
    for arm in ("B", "C"):
        output = study / "units" / unit_id / arm
        bundle.arm_output=output
        measurement, response = bundle.load(output / "owner-measurement.json"), bundle.load(output / "arm-response.json")
        resource = bundle.load(bundle.link(measurement["evidence"]["resource_audit"]))
        require(resource["resource_envelope"]==registration["config"]["resource_envelope"] and response["resource_envelope"]==registration["config"]["resource_envelope"],"Shared registered resource envelope differs")
        require(not resource["failed_model_attempt_dirs"], "Failed requests need their separate conservative-usage audit")
        cpu = [bundle.resolve(p) for p in response["cpu_execution_dirs"]]
        models = [bundle.resolve(p) for p in response["model_evidence_dirs"]]
        require(len(cpu) == len(set(cpu)) and len(models) == len(set(models)), "Repeated receipt paths in actual resource inventory")
        require(set(cpu) == {bundle.resolve(p) for p in resource["cpu_execution_dirs"]} and set(models) == {bundle.resolve(p) for p in resource["completed_model_evidence_dirs"]}, "Resource inventories disagree")
        envelope=registration["config"]["resource_envelope"]
        require(len(cpu)<=envelope["actual_cpu_executions_per_unit"] and len(models)<=envelope["proposal_calls_per_unit"],"Actual resources exceed original shared unit allowance")
        cpu_results = {p: replay_cpu(bundle, p) for p in cpu}
        selected = bundle.resolve(response["selected_run_dir"])
        require(selected in cpu_results, "Selected CPU result absent from actual inventory")
        metrics, model, rows, _ = cpu_results[selected]
        require(measurement["unit_id"]==unit_id and measurement["arm"]==arm and measurement["model_id"]==registration["config"]["model_id"],"Owner scalar receipt condition differs")
        require(all(rows[s] == public["task_bundle"][s] for s in rows), "CPU data differs from registered task")
        require(not {r["id"] for r in owner["test"]} & {r["id"] for s in rows.values() for r in s}, "Owner test overlaps public data")
        test_mse = owner_metric(owner["test"],model)
        require(equal(test_mse, measurement["test_mse"]) and equal(metrics["validation_mse"], measurement["validation_mse"]), "Independent owner/public metric differs")
        raw = [replay_model(bundle, p, registration["config"]["model_id"], registration["config"]["resource_envelope"]["reasoning_effort"]) for p in models]
        measures = {"input_tokens": sum(x[0] for x in raw), "output_tokens": sum(x[1] for x in raw),
                    "model_seconds": math.fsum(x[2] for x in raw), "provider_attempts": len(raw),
                    "actual_cpu_executions": len(cpu), "total_cpu_execution_seconds": math.fsum(x[3] for x in cpu_results.values())}
        require(all(equal(v, resource["measures"][k]) for k, v in measures.items()), "Raw resource totals differ from owner audit")
        for name in ("report-review.json", "companion-review.json"):
            review = bundle.load(output / name)
            require(review["reviewer_role"] == "independent_verifier" and review["status"] == "complete" and review["pending_claims"] == 0 and review["unsupported_claims"] == 0, "Historical independent review not complete")
        arms[arm] = {**metrics, "test_mse": test_mse, **measures}
    b, c = arms["B"], arms["C"]
    return {"valid": True, "kind": "relocated_published_development_metric_resource_replay", "unit_id": unit_id,
            "registration_sha256": REGISTRATION_SHA256,"publication_manifest_sha256":PUBLICATION_SHA256, "arms": arms,"regenerated_owner_proof":owner_proof,
            "token_relative_reduction": 1 - (c["input_tokens"] + c["output_tokens"]) / (b["input_tokens"] + b["output_tokens"]),
            "test_mse_relative_reduction": 1 - c["test_mse"] / b["test_mse"],
            "actual_model_calls": 0, "new_runner_executions": 0,
            "calculation_source_sha256": sha(__file__), "adopted": False,
            "scope": "Original bytes preserved; independent fit/prediction/owner-MSE and raw provider usage replay. Historical report reviews checked for declared status only, not freshly semantically adjudicated. Minimal-phase development diagnostic, never original-default superiority or final adoption."}


def replay(root,recorded_root,study,units,registration_sha256=REGISTRATION_SHA256,
           publication_manifest="evidence/publication-review-completed-v4/manifest.json",publication_sha256=PUBLICATION_SHA256):
    require(units and len(units)==len(set(units)),"Distinct explicit units required")
    bundle,folder,registration,publication=prepare_bundle(root,recorded_root,study,registration_sha256,publication_manifest,publication_sha256)
    results=[replay_unit(bundle,folder,registration,publication,unit) for unit in units]
    return {"valid":True,"kind":"externally_pinned_published_development_units_replay","units":results,
        "registration_sha256":registration_sha256,"publication_manifest_sha256":publication_sha256,
        "all_checked_file_sha256":bundle.checked,"checked_original_files":len(bundle.checked),
        "new_model_calls":0,"new_runner_executions":0,"private_owner_files_opened":False,"owner_requests_opened":False,
        "test_rows_printed_or_persisted":False,"calculation_source_sha256":sha(__file__),"adopted":False}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--recorded-root",required=True)
    parser.add_argument("--study",default="runs/development/paired-pilot-v4")
    parser.add_argument("--units",nargs="+",required=True)
    parser.add_argument("--registration-sha256",default=REGISTRATION_SHA256)
    parser.add_argument("--publication-manifest",default="evidence/publication-review-completed-v4/manifest.json")
    parser.add_argument("--publication-sha256",default=PUBLICATION_SHA256)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=replay(args.root,args.recorded_root,args.study,args.units,args.registration_sha256,args.publication_manifest,args.publication_sha256)
    require(not args.out.exists(),"Preserve prior replay result; choose a new output")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"valid":result["valid"],"units":[{k:v for k,v in unit.items() if k in ("unit_id","arms","test_mse_relative_reduction","token_relative_reduction")} for unit in result["units"]],"private_owner_files_opened":False,"test_rows_printed_or_persisted":False},ensure_ascii=True))
