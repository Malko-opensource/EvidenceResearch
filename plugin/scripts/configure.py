"""Create a local plugin marketplace with explicit, shared research connections.

This does not install into the user's Codex profile, start a server, or run research.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def configure(source, output, interpreter, root, port):
    source, output = source.resolve(), output.resolve()
    interpreter, root = interpreter.resolve(strict=True), root.resolve(strict=True)
    if not interpreter.is_file() or not root.is_dir():
        raise ValueError("Python must be a file and research root must be a directory")
    if output.exists():
        raise ValueError("Output already exists; choose a new directory")
    if output == source or output in source.parents or source in output.parents:
        raise ValueError("Output must be separate from the source plugin")
    if output == root or output in root.parents or root in output.parents:
        raise ValueError("Output must be separate from the live research root")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    probe = subprocess.run(
        [str(interpreter), "-I", "-c",
         "import json, research_cli, mcp, mcp_types; "
         "print(json.dumps({'version':research_cli.__version__}))"],
        cwd=str(source), capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if probe.returncode:
        raise ValueError("The specified Python needs an installed research-state-cli[mcp]: " + probe.stderr.strip())
    installed = json.loads(probe.stdout)
    name = json.loads((source / "plugin.json").read_text(encoding="utf-8"))["name"]
    output.mkdir(parents=True)
    destination = output / name
    destination.mkdir()
    # Only explicit package files are copied. Research data, environments and
    # credentials are never bundled; this is not a source-code fork of the CLI.
    for relative in ("plugin.json", ".codex-plugin/plugin.json"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    shutil.copytree(source / "skills", destination / "skills")
    shutil.copytree(source / "scripts", destination / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    args = ["-I", "-m", "research_cli.mcp_server", "--root", str(root)]
    # Portable Agent Plugins require a bare executable name or contained ./ path.
    # This PATH belongs only to the MCP child; the machine PATH is unchanged.
    server = {"command": interpreter.name, "args": args,
              "env": {"PATH": str(interpreter.parent) + os.pathsep + os.environ.get("PATH", "")}}
    dump(destination / ".mcp.json", {"mcpServers": {"research_state": server}})
    dump(destination / "mcp.json", {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {"research_state": {"type": "stdio", **server}},
    })
    connection = {
        "schema_version": 1, "research_root": str(root),
        "workspace_rule": "A tool workspace is relative to research_root; CLI uses the same absolute directory.",
        "python": str(interpreter), "installed_cli_version": installed["version"],
        "cli_command": [str(interpreter), "-I", "-m", "research_cli"],
        "mcp_command": [str(interpreter), *args],
        "web_command": [str(interpreter), "-I", "-m", "research_cli.web_server",
                        "--root", str(root), "--port", str(port)],
        "web_url": "http://127.0.0.1:" + str(port) + "/",
        "models_called_by_plugin": False,
        "starts_web_or_research_on_install": False,
    }
    dump(destination / "connection.json", connection)
    marketplace = {
        "name": "evidence-research-local",
        "interface": {"displayName": "EvidenceResearch Local"},
        "plugins": [{"name": name,
                     "source": {"source": "local", "path": "./" + name},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Engineering"}],
    }
    dump(output / ".agents/plugins/marketplace.json", marketplace)
    archive = output / (name + ".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(destination.rglob("*")):
            if file.is_file():
                bundle.write(file, file.relative_to(output).as_posix())
    return {"ok": True, "marketplace_root": str(output), "plugin_root": str(destination),
            "connection": connection, "archive": str(archive),
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New local marketplace directory")
    parser.add_argument("--python", required=True, type=Path, help="Installed MCP-capable Python executable")
    parser.add_argument("--root", required=True, type=Path, help="Existing directory of relative research workspaces")
    parser.add_argument("--port", default=8765, type=int, help="Web command port; no server is started")
    options = parser.parse_args(argv)
    try:
        result = configure(Path(__file__).resolve().parents[1], options.output,
                           options.python, options.root, options.port)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": {"code": "PLUGIN_CONFIGURATION", "message": str(error)}}))
        return 2
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
