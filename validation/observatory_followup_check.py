"""Read-only runtime/provenance checks for the spectator UI follow-up.

This script does not call /api/call, run an experiment, repair an artifact,
initialize a workspace, read capability keys, or change an existing database.
Browser layout, native WebMCP and visual truthfulness are separate checks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen


PROJECT = Path(__file__).resolve().parents[1]
WORKSPACES = (PROJECT / "research-workspaces").resolve()
PROOF = (PROJECT / "validation/observatory-followup-20261004").resolve()
BASELINE = PROOF / "state-before.json"
FIXTURE_MANIFEST = PROJECT / "validation/product-web-0.7.0/fixture.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def state_fingerprint():
    """Hash logical SQLite rows instead of checkpoint-sensitive SQLite bytes."""
    databases, evidence, launch_markers = {}, {}, {}
    for database in sorted(WORKSPACES.rglob("state.sqlite3")):
        if database.parent.name != ".research":
            continue
        resolved = database.resolve()
        if not resolved.is_relative_to(WORKSPACES):
            raise RuntimeError("Workspace database leaves the explicitly named scope")
        relative = resolved.relative_to(WORKSPACES).as_posix()
        with sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("BEGIN")
            dumped = "\n".join(connection.iterdump()).encode("utf-8")
            revision = int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
            databases[relative] = {"logical_sha256": digest(dumped), "revision": revision}
        directory = database.parent / "evidence"
        if directory.is_dir():
            for blob in sorted(directory.iterdir()):
                if not blob.is_file():
                    continue
                resolved_blob = blob.resolve()
                if not resolved_blob.is_relative_to(directory.resolve()):
                    raise RuntimeError("Evidence link leaves its workspace evidence directory")
                evidence[resolved_blob.relative_to(WORKSPACES).as_posix()] = digest(resolved_blob.read_bytes())
    for marker in sorted(WORKSPACES.glob("*/launch-count.txt")):
        launch_markers[marker.relative_to(WORKSPACES).as_posix()] = digest(marker.read_bytes())
    modules = {path.name: digest(path.read_bytes()) for path in sorted((PROJECT / "research_cli").glob("*.py"))}
    return {"databases": databases, "evidence": evidence, "launch_markers": launch_markers, "core_modules": modules}


def fetch(base, path):
    with urlopen(base + path, timeout=15) as response:
        return response.status, dict(response.headers.items()), response.read()


def get_json(base, path):
    status, _, body = fetch(base, path)
    envelope = json.loads(body)
    if status != 200 or envelope.get("ok") is not True:
        raise RuntimeError("Read-only HTTP request failed: " + path + ": " + json.dumps(envelope, ensure_ascii=False))
    return envelope["data"]


def runtime_check(base):
    bootstrap = get_json(base, "/api/bootstrap")
    # Keep session_token out of output and saved proof.
    report = {"version": bootstrap["version"], "http_tool_count": len(bootstrap["tools"]), "assets": {}, "modules": {}}
    installed_web = PROJECT / ".validation-venv/Lib/site-packages/research_cli/web"
    for source in sorted((PROJECT / "research_cli/web").iterdir()):
        if not source.is_file():
            continue
        status, headers, served = fetch(base, "/" + source.name)
        installed = installed_web / source.name
        report["assets"][source.name] = {
            "status": status, "source_sha256": digest(source.read_bytes()),
            "served_sha256": digest(served),
            "installed_sha256": digest(installed.read_bytes()) if installed.is_file() else None,
            "source_matches_http": source.read_bytes() == served,
            "source_matches_installed": installed.is_file() and source.read_bytes() == installed.read_bytes(),
            "no_store": headers.get("Cache-Control") == "no-store",
        }
    report["assets_match"] = all(item["source_matches_http"] and item["source_matches_installed"]
                                  and item["status"] == 200 and item["no_store"]
                                  for item in report["assets"].values())
    installed_package = installed_web.parent
    for source in sorted((PROJECT / "research_cli").glob("*.py")):
        installed = installed_package / source.name
        report["modules"][source.name] = {
            "source_sha256": digest(source.read_bytes()),
            "installed_sha256": digest(installed.read_bytes()) if installed.is_file() else None,
            "source_matches_installed": installed.is_file() and source.read_bytes() == installed.read_bytes(),
        }
    report["modules_match"] = all(item["source_matches_installed"] for item in report["modules"].values())
    workspace_page = get_json(base, "/api/workspaces?limit=100")
    report["workspaces"] = workspace_page["items"]
    report["snapshots"] = {}
    for name in ("goal-plugin-demo-20261004", "agent-observatory-20261004",
                 "product-empty-20261004", "product-fixtures-20261004"):
        path = "/api/snapshot?" + urlencode({"workspace": name, "limit": 6})
        first, second = get_json(base, path), get_json(base, path)
        if first["status"] != second["status"] or first["events"] != second["events"]:
            raise RuntimeError("Persisted status/events changed during repeated read-only snapshots: " + name)
        goal_report = second.get("report")
        if goal_report and not goal_report.get("consistent"):
            raise RuntimeError("Snapshot revisions disagree: " + name)
        report["snapshots"][name] = {"revision": second["status"]["revision"],
                                    "registration_count": second["status"]["total"],
                                    "page_records": len(second["status"]["registrations"]),
                                    "report_consistent": goal_report.get("consistent") if goal_report else None}
    if report["snapshots"]["product-empty-20261004"]["registration_count"] != 0:
        raise RuntimeError("Existing empty fixture is no longer empty")
    fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    if report["snapshots"][fixture["workspace"]]["registration_count"] != fixture["registration_count"]:
        raise RuntimeError("Existing many-record fixture count changed")
    report["fixture_records"] = []
    for label, expected in (("success", ("succeeded", "passed", "adopted")),
                            ("failure", ("succeeded", "failed", "rejected")),
                            ("unexecuted", (None, None, "pending"))):
        path = "/api/snapshot?" + urlencode({"workspace": fixture["workspace"], "registration": fixture[label], "limit": 6})
        selected = get_json(base, path)
        record = next(item for item in selected["report"]["records"] if item["registration"]["id"] == fixture[label])
        actual = (record["run"]["state"] if record.get("run") else None,
                  record["verification"]["state"] if record.get("verification") else None,
                  record["decision"]["state"])
        if actual != expected:
            raise RuntimeError("Fixture source states changed: " + label + ": " + repr(actual))
        report["fixture_records"].append({"label": label, "registration": fixture[label],
                                          "execution": actual[0], "verification": actual[1], "decision": actual[2],
                                          "evidence_integrity": [item.get("integrity") for item in record["evidence"]]})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "after"))
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--require-assets", action="store_true", help="Fail unless source/installed/served assets and Python modules match")
    args = parser.parse_args()
    url = urlsplit(args.base)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.path not in ("", "/") or url.query or url.fragment:
        raise ValueError("This probe only accepts the local loopback service")
    PROOF.mkdir(parents=True, exist_ok=True)
    before = state_fingerprint()
    runtime = runtime_check(args.base.rstrip("/"))
    after = state_fingerprint()
    persisted_state_unchanged = before == after
    baseline_matches = None
    if args.phase == "before":
        if BASELINE.exists():
            raise RuntimeError("Preserving the original pre-change baseline; use phase after")
        BASELINE.write_text(json.dumps(before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        baseline_matches = {key: baseline[key] == after[key] for key in baseline}
    report = {"ok": persisted_state_unchanged and (baseline_matches is None or all(baseline_matches.values()))
                       and (not args.require_assets or (runtime["assets_match"] and runtime["modules_match"])),
              "phase": args.phase, "checked_at": datetime.now(timezone.utc).isoformat(),
              "base": args.base, "read_only_http": True, "calls_model": False,
              "starts_experiment": False, "reads_capability_keys": False,
              "persistent_state_unchanged_during_reads": persisted_state_unchanged,
              "matches_before_baseline": baseline_matches, "runtime": runtime,
              "limits": ["Browser layout and native WebMCP must be checked separately", "Not a research performance comparison"]}
    output = PROOF / ("runtime-" + args.phase + ".json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "phase": args.phase, "assets_match": runtime["assets_match"], "modules_match": runtime["modules_match"],
                      "persistent_state_unchanged_during_reads": persisted_state_unchanged,
                      "matches_before_baseline": baseline_matches, "proof": str(output)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
