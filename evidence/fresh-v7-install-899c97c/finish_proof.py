"""Archive only the completed new public engineering proof; executes no tests."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROOF = HERE / "fresh-public-run-v1"
TEMP = HERE.parents[2] / "_t7p899c97cd" / "captured38"

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def create(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def row(path: Path) -> dict:
    return {"path": path.relative_to(HERE).as_posix(),
            "bytes": path.stat().st_size, "sha256": digest(path)}

def main() -> None:
    external_pins = {
        "parent-go-v1.json": "704687493bff004578116153e80485deda942615a8f6db42e3b103e656b22002",
        "parent-checkout-receipt-v1.json": "9e1e64c107d5477213ed2cb0f406c206439cd76c43f1d14185fdff778c7dae59",
        "parent-upstream-acquisition-receipt-v1.json": "e7370b53c22f0a3268b7363a3385ddc7a2ba868affaee2a76e16c8abb04d68e6",
        "validate_public.py": "f6dc3735eca1430e1902bd967e753d9dec8a53a11dd810104f0e873676539760",
        "audit_guard.py": "ca74d613e347b5b094027bd233c91408b56fcc981e1ee1932b733fae4f84d2bd",
        "expected-source71.json": "cf3dce0b8b81c885de0e7c813827b30b36dda997eef8ec76d987fe804c117977",
        "expected-upstream35.json": "f852a10e1f67f4518344e7ec15ae4ff1379d1300dc9936ccc8c236bfe43c1a66",
        "expected-independent84.json": "2368762de07766643e6cdcd7461ea3448c93028cac9491bae5c1a6c4224f8694",
        "fresh-public-run-v1/result.json": "492829dbb0dd954e008b67be34e4ded3ccd0199e404b372b9dcdf0b239dd3c8a",
    }
    for name, expected in external_pins.items():
        assert digest(HERE / name) == expected, name
    result = load(PROOF / "result.json")
    before, after = load(PROOF / "before.json"), load(PROOF / "after.json")
    assert result["valid"] is True and result["checks"] == 263
    assert before["source106"] == after["source106"]
    assert len(before["source106"]) == 106
    assert result["public_commit"] == "899c97cdab5d557db8b80a6bf479779ed13282d1"
    assert result["full_suite_executed_once"] is True
    assert len(result["phases"]) == 7
    for phase in result["phases"]:
        assert phase["exit_code"] == 0
        for channel in ("stdout", "stderr"):
            path = PROOF / (phase["phase"] + "." + channel + ".log")
            assert digest(path) == phase[channel + "_sha256"]
    unit_guard = load(PROOF / "unit-guard.json")
    replay_guard = load(PROOF / "captured38-guard.json")
    assert all(value == 0 for key, value in unit_guard["counts"].items()
               if key != "allowed_cpu_fixture_subprocesses")
    assert unit_guard["counts"]["allowed_cpu_fixture_subprocesses"] == 1
    assert all(value == 0 for value in replay_guard["counts"].values())
    assert digest(TEMP / "result.json") == result["captured38_result_sha256"]
    captured = load(TEMP / "result.json")
    assert captured["status"] == "pass" and captured["tests_run"] == 38
    assert captured["failures"] == captured["errors"] == 0
    assert captured["actual_provider_calls"] == captured["research_trials"] == 0
    assert captured["trusted_cpu_component_executions"] == 12
    assert all(value == 0 for value in captured["guards"].values())
    logs = [item for item in captured["artifacts"] if item["path"] == "tests.log"]
    assert len(logs) == 1 and digest(TEMP / "tests.log") == logs[0]["sha256"]
    for source, target in ((TEMP / "result.json", PROOF / "captured38-result.json"),
                           (TEMP / "tests.log", PROOF / "captured38-tests.log")):
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        assert digest(target) == digest(source)
    receipt = {
        "kind": "fresh_public_v7_completed_engineering_proof_audit",
        "public_commit": result["public_commit"],
        "external_pins": external_pins,
        "phase_count": 7, "phase_logs_hash_checked": True,
        "runtime_sources_compared": 106, "runtime_source_bytes_unchanged": True,
        "full_suite": {"checks": 263, "runs_in_new_environment": 1,
                       "raw_stderr": row(PROOF / "full263.stderr.log")},
        "captured_source": {"checks": 38, "runs_in_new_public_checkout": 1,
                            "trusted_tiny_cpu_components": 12,
                            "actual_provider_calls": 0,
                            "raw_result": row(PROOF / "captured38-result.json"),
                            "raw_tests_log": row(PROOF / "captured38-tests.log"),
                            "captured_artifact_inventory_rows": len(captured["artifacts"]),
                            "artifact_bodies_reaudited_by_this_finisher": False},
        "guards": {"unit": unit_guard, "captured": replay_guard},
        "private_owner_or_actual_research_access": False,
        "credential_access_or_model_authentication_assessment": False,
        "clone_fetch_git_network_in_finisher": False,
        "successful_phase_reruns": 0,
        "supplemental_five_portability_claim": False,
        "framework_improvement_or_goal_completion_claim": False,
        "source_validation_scope": "106 metadata entries previously verified by the pinned validate helper; this finisher compares before/after metadata only and does not reopen any runtime source.",
        "guard_limit": "Parent Python audit hook; the one allowed registered CPU fixture child replaces PYTHONPATH and is outside that hook. This is not an OS sandbox or a global filesystem proof.",
    }
    create(PROOF / "complete-receipt.json", receipt)
    report = """새 공개 v7 설치·재현 결과

공개 커밋 `899c97cdab5d557db8b80a6bf479779ed13282d1`을 부모가 새 `_er7`에 내려받고 고정 upstream 35개를 별도 취득한 뒤, 외부 해시로 고정한 helper와 GO에 따라 새 자체 `.venv`를 만들었다. 공개 소스 71개와 자체 upstream 35개, 총 106개를 확인했고 설치·검사 전후 바이트가 같았다. 선택에서 빠진 두 선택적 구형 example은 사용하지 않았다.

네트워크 없이 editable 설치가 성공했다. 설치 때만 bundled build 도구를 사용하고 실행·검사의 PATH/PYTHONPATH에서는 해당 도구를 제거했다. 자체 환경의 package 버전은 `0.4.0.dev0`, user site는 비활성화였다. CLI help와 고정 reference closure가 통과했다. 모델 인증은 확인하지 않았다.

새 환경에서 전체 263개 검사를 한 번 실행해 모두 통과했다. 공개된 고정 캡처 소스의 38개 사례도 새 공개 체크아웃과 새 짧은 출력 경로에서 한 번 재현해 통과했다. 이 재현은 합성 transport와 작은 공개 배열 CPU 구성 검사 12회이며, 실제 provider 호출과 연구 trial은 없었다. 원시 로그·명령·receipt와 가드 기록을 보존했다.

부모 Python 가드는 기존 프로젝트 접근, 허용 root 밖 접근, 미등록 run 접근, 미허용 process, network 이벤트를 모두 0으로 기록했다. 전체 검사에서 허용된 CPU fixture 자식 1개는 PYTHONPATH를 교체하여 이 부모 hook 밖에서 실행된다. 따라서 이 기록은 OS sandbox나 모든 자식의 파일 접근에 대한 전역 증명이 아니다. 38개 구성 재현에서는 부모 guard count와 고정 driver의 기존 root/provider guard count가 모두 0이었다.

이번 증거는 공개 선택 소스의 설치·구성 재현 가능성에 한정한다. 별도 supplemental 5개 sidecar의 portable 재실행, 실제 모델 인증, 연구 성능 향상, Goal 완료를 주장하지 않는다. 기존 실제 v5/v6/v7 기록, owner 행·private seed, 기존 309개 소스 body는 열지 않았다. 성공한 단계를 반복하지 않았고 Git 변경이나 업로드도 하지 않았다.

공개 후보는 `public-proof-selection-v1.json`의 exact 목록으로 제안한다. helper/가드/외부 pin/부모 취득 receipt와 새 7단계 원시 로그·106개 source metadata·38개 원시 result/tests log만 포함한다. `.venv`, 새 runtime upstream body, 전체 합성 출력 tree, 기존 실제 연구 자료는 제외한다. 38개 raw result의 artifact inventory는 보존하지만 finisher가 그 모든 artifact body를 다시 감사했다는 주장은 하지 않는다.
"""
    with (PROOF / "report.ko.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    top_names = list(external_pins)[:8] + ["finish_proof.py"]
    top_names += [prefix + suffix for prefix in ("verify", "validate")
                  for suffix in ("-invocation.json", ".stdout.log", ".stderr.log")]
    selected = [HERE / name for name in top_names]
    selected += sorted((p for p in PROOF.iterdir() if p.is_file()), key=lambda p: p.name)
    assert len(selected) == len(set(selected))
    create(HERE / "public-proof-selection-v1.json", {
        "kind": "exact_new_public_v7_engineering_proof_publication_candidate",
        "public_commit": result["public_commit"],
        "file_count": len(selected), "bytes": sum(p.stat().st_size for p in selected),
        "files": [row(p) for p in selected],
        "scope": "New own-environment engineering proof and source-only metadata; no actual research/private owner data, no complete synthetic output body selection.",
        "supplemental_five_portable": False,
        "publication_executed": False,
    })
    print(json.dumps({"complete_receipt_sha256": digest(PROOF / "complete-receipt.json"),
                      "report_sha256": digest(PROOF / "report.ko.md"),
                      "public_selection_sha256": digest(HERE / "public-proof-selection-v1.json"),
                      "files": len(selected)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
