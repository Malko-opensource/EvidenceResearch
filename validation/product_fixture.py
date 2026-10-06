"""Actual model-free dashboard fixtures; these are not research performance evaluations."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_cli.core import Store, sha256_file
from research_cli.runner import run, verify

NAME = "product-fixtures-20261004"
WORKSPACE = (ROOT / "research-workspaces" / NAME).resolve()
PROOF = (ROOT / "validation" / "product-web-0.7.0").resolve()
MANIFEST = PROOF / "fixture.json"
PURPOSE = "상황판 개발용 fixture · 연구 성능 평가가 아님"
TITLE = "상황판 개발용 fixture · 가중 평균의 성공·실패·미실행"


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source(path, text):
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise RuntimeError("Existing fixture source differs; preserving it: " + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def main():
    if WORKSPACE != (ROOT / "research-workspaces").resolve() / NAME or not PROOF.is_relative_to(ROOT / "validation"):
        raise RuntimeError("Fixture paths leave their explicitly named project scope")
    if WORKSPACE.exists() and not MANIFEST.exists():
        raise RuntimeError("Existing directory has no fixture manifest; preserving it without changes")
    PROOF.mkdir(parents=True, exist_ok=True)
    data = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {
        "purpose": PURPOSE, "workspace": NAME, "goal_title": TITLE, "registrations": []}
    if data.get("purpose") != PURPOSE or data.get("workspace") != NAME:
        raise RuntimeError("Fixture manifest identity mismatch")
    save(MANIFEST, data)
    Store.init(WORKSPACE)
    store = Store(WORKSPACE)
    if "goal" not in data:
        data["goal"] = store.goal_create(TITLE, PURPOSE + "; 고정 입력 [2,4,10], 가중치 [1,2,1]. 두 실제 실행과 30개 미실행 등록으로 표시·페이징을 검사한다.")["id"]
        save(MANIFEST, data)
    for mode, statement in (("correct", "가중치를 반영한 평균은 독립 기준 5와 일치한다."),
                            ("naive", "가중치를 생략한 단순 평균도 독립 기준 5를 충족할 수 있다.")):
        key = mode + "_hypothesis"
        if key not in data:
            data[key] = store.hypothesis_create(data["goal"], PURPOSE + "; " + statement)["id"]
            save(MANIFEST, data)
    marker = WORKSPACE / "launch-count.txt"
    for mode in ("correct", "naive"):
        calculation = "sum(x*w for x,w in zip(values,weights))/sum(weights)" if mode == "correct" else "sum(values)/len(values)"
        source(WORKSPACE / mode / "task.py", "import json\nfrom pathlib import Path\nvalues=[2,4,10]\nweights=[1,2,1]\n"
               + f"mean={calculation}\nPath('result.json').write_text(json.dumps({{'weighted_mean':mean}}),encoding='utf-8')\n"
               + f"with Path({str(marker)!r}).open('a',encoding='utf-8') as marker:\n    marker.write({mode!r}+'\\n')\n")
    validator = WORKSPACE / "validator.py"
    source(validator, "import json,math,sys\nfrom pathlib import Path\nbundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
           "observed=json.loads(Path(bundle['artifacts']['result']).read_text(encoding='utf-8'))['weighted_mean']\n"
           "expected=(2*1+4*2+10*1)/(1+2+1)\nvalid=isinstance(observed,(int,float)) and not isinstance(observed,bool) and math.isfinite(observed)\n"
           "if not valid: raise ValueError('Artifact does not contain a finite measured mean')\n"
           "print(json.dumps({'metrics':{'weighted_mean':observed,'pass_rate':float(observed==expected)},"
           "'details':{'development_fixture':True,'independent_expected_mean':expected,'observed_mean':observed,'basis':'Fixed public values [2,4,10], weights [1,2,1]'}}))\n")
    store.validator_register("product-weighted-fixed-v1", [store.runner_interpreter(), str(validator), "{bundle}"],
                             store.owner_key_path.read_text(encoding="utf-8").strip())
    calls = []
    for index in range(32):
        mode = "naive" if index == 1 else "correct"
        directory = WORKSPACE / mode
        spec = {"hypothesis_id": data[mode + "_hypothesis"],
                "change": PURPOSE + "; " + ("가중치를 반영한 평균 계산" if index == 0 else "가중치를 생략한 단순 평균 계산" if index == 1 else f"미실행 페이지 검사 등록 {index + 1:02d}"),
                "comparison": "고정 독립 기대값 weighted_mean=5; 성능 비교가 아닌 계산·표시 개발 실연",
                "data_split": {"development": "공개 고정 입력 [2,4,10], 가중치 [1,2,1]; 무차원 수치",
                               "evaluation": "동일 입력의 owner-frozen 독립 계산 기준; 연구 성능 평가에서 제외"},
                "seed": 0 if index < 2 else index - 1,
                "source_version": {"label": "product-weighted-" + mode + "-v1", "files": {"task.py": sha256_file(directory / "task.py")}},
                "metrics": ["weighted_mean", "pass_rate"], "metric_units": {"weighted_mean": "무차원", "pass_rate": "비율"},
                "criteria": [{"metric": "weighted_mean", "op": "==", "threshold": 5}, {"metric": "pass_rate", "op": ">=", "threshold": 1}],
                "conditions": {"purpose": PURPOSE, **({"unexecuted_page_fixture": index + 1} if index >= 2 else {})},
                "command": [store.runner_interpreter(), "task.py"], "cwd": str(directory),
                "artifacts": [{"name": "result", "path": "result.json"}], "validator": "product-weighted-fixed-v1"}
        registration = store.register(data["goal"], spec, request_key=f"product-fixture-registration-{index}")["registration"]["id"]
        if index < len(data["registrations"]):
            if data["registrations"][index] != registration:
                raise RuntimeError("Existing fixture registration identity mismatch")
        else:
            data["registrations"].append(registration)
            save(MANIFEST, data)
        if index < 2:
            result = run(store, registration, request_key=f"product-fixture-run-{index}")
            if result["record"]["run"]["state"] not in ("succeeded", "failed"):
                raise RuntimeError("Execution is unknown/running: inspect and recover the original worker; do not rerun")
            verified = verify(store, registration)
            record = verified["record"]
            calls.append({"registration": registration, "execution_started": result["started"],
                          "verification_reused": verified.get("reused", False)})
            expected = "passed" if index == 0 else "failed"
            if record["verification"]["state"] != expected:
                raise RuntimeError("Actual fixed verifier result differed from this development fixture's expected condition")
            decision = "adopted" if index == 0 else "rejected"
            if record["decision"]["state"] == "pending":
                store.decide(registration, decision, PURPOSE + "; " + ("가중 평균 5가 독립 기준과 일치한다." if index == 0 else "가중치를 생략해 16/3을 얻었다. 실행은 성공했지만 등록된 가중 평균 5와 불일치하여 기각한다."))
    records = [store.show(registration) for registration in data["registrations"][:3]]
    marker_lines = marker.read_text(encoding="utf-8").splitlines()
    if marker_lines != ["correct", "naive"] or store.status(limit=100)["total"] != 32:
        raise RuntimeError("Fixture execution count or registration count differs; preserving all records")
    data.update({"success": data["registrations"][0], "failure": data["registrations"][1], "unexecuted": data["registrations"][2],
                 "actual_execution_count": 2, "registration_count": 32, "launch_marker": str(marker), "revision": store.revision()})
    save(MANIFEST, data)
    report = {**data, "records": [{"registration": record["registration"]["id"], "execution": record["run"]["state"] if record["run"] else "registered",
              "verification": record["verification"]["state"] if record["verification"] else "pending", "decision": record["decision"]["state"],
              "metrics": record["verification"]["metrics"] if record["verification"] else {},
              "result_evidence": [{"id": evidence["id"], "path": str(WORKSPACE / evidence["path"]), "sha256": evidence["sha256"]}
                                  for evidence in record["evidence"] if evidence["name"] == "result"]} for record in records],
              "launch_marker_lines": marker_lines, "run_calls": calls, "external_model_usage": "unknown", "fixture_llm_calls": 0,
              "reproduction": {"prepare": [sys.executable, str(Path(__file__).resolve())],
                               "status_page": [sys.executable, "-m", "research_cli", "--workspace", str(WORKSPACE), "status", "--limit", "5", "--offset", "20"],
                               "show_success": [sys.executable, "-m", "research_cli", "--workspace", str(WORKSPACE), "show", data["success"]]}}
    save(PROOF / "fixture-report.json", report)
    print(json.dumps({key: report[key] for key in ("purpose", "workspace", "goal_title", "success", "failure", "unexecuted", "actual_execution_count", "registration_count", "revision")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
