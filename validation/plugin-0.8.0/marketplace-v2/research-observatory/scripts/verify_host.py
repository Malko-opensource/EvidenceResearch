"""Verify a prepared plugin in an isolated Codex home without a model turn.

Records actual marketplace installation and app-server skill discovery. No user
credentials or global Codex configuration are copied into the validation home.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading


def verify(marketplace, output, codex):
    marketplace = marketplace.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise ValueError("Validation output already exists")
    output.mkdir(parents=True)
    host_home = output / "codex-home"
    host_home.mkdir()
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(host_home)
    records = []

    def command(arguments):
        result = subprocess.run([codex, *arguments], cwd=marketplace, env=environment,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        records.append({"command": [codex, *arguments], "exit_code": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            raise RuntimeError("Codex host command failed: " + arguments[0])
        return result.stdout

    version = command(["--version"]).strip()
    command(["plugin", "marketplace", "add", str(marketplace), "--json"])
    command(["plugin", "add", "research-observatory@evidence-research-local", "--json"])
    command(["plugin", "list", "--marketplace", "evidence-research-local", "--json"])
    incoming = queue.Queue()
    errors = []
    process = subprocess.Popen([codex, "app-server", "--stdio"], cwd=marketplace,
                               env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)
    def drain(stream, sink):
        for line in stream:
            sink(line.rstrip())
    threading.Thread(target=drain, args=(process.stdout, incoming.put), daemon=True).start()
    threading.Thread(target=drain, args=(process.stderr, errors.append), daemon=True).start()
    messages = []

    def request(identifier, method, parameters):
        message = {"id": identifier, "method": method, "params": parameters}
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()
        messages.append({"direction": "request", "message": message})
        while True:
            line = incoming.get(timeout=60)
            response = json.loads(line)
            messages.append({"direction": "response", "message": response})
            if response.get("id") == identifier:
                if "error" in response:
                    raise RuntimeError("Codex app-server error: " + str(response["error"]))
                return response["result"]

    try:
        request(1, "initialize", {"clientInfo": {"name": "research-plugin-validation", "version": "0.8.0"},
                                  "capabilities": {"experimentalApi": True}})
        process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
        process.stdin.flush()
        skills = request(2, "skills/list", {"cwds": [str(marketplace)], "forceReload": True})
        found = [skill for entry in skills.get("data", []) for skill in entry.get("skills", [])
                 if skill.get("name") in ("research-goal", "research-observatory:research-goal")]
        if not found or not found[0].get("enabled"):
            raise RuntimeError("Installed research-goal skill was not discovered as enabled")
        mcp_status = request(3, "mcpServerStatus/list", {"limit": 20, "detail": "toolsAndAuthOnly"})
        record = {"ok": True, "host_version": version, "isolated_codex_home": str(host_home),
                  "marketplace": str(marketplace), "commands": records,
                  "discovered_skills": found, "mcp_status": mcp_status, "app_server_messages": messages,
                  "app_server_stderr": errors, "model_turn_requested": False,
                  "global_profile_modified": False}
        (output / "host-discovery.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        (output / "commands.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "app-server.json").write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "app-server-stderr.log").write_text("\n".join(errors), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--codex", default=shutil.which("codex"))
    options = parser.parse_args()
    if not options.codex:
        parser.error("Codex CLI not found; specify --codex")
    result = verify(options.marketplace, options.output, options.codex)
    print(json.dumps({"ok": result["ok"], "host_version": result["host_version"],
                      "skills": [skill["name"] for skill in result["discovered_skills"]]}))


if __name__ == "__main__":
    main()
