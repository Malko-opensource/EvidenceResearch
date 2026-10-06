"""Probe the installed stdio launcher from the actual local Codex config.

Development installation check only; does not run a model or experiment.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import sys
import tomllib
import uuid

from mcp import Client, StdioServerParameters
from research_cli.web_tools import tool_descriptions


PROJECT = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / ".codex" / "config.toml"
VERSION = metadata.version("research-state-cli")
OUTPUT = PROJECT / "validation" / ("mcp-installation-" + VERSION + ".json")


async def main():
    original_config = CONFIG.read_bytes()
    config = tomllib.loads(original_config.decode("utf-8"))
    own = config["mcp_servers"]["research_state"]
    assert own["command"] == str(PROJECT / ".mcp-venv" / "Scripts" / "python.exe")
    assert own["args"] == ["-I", "-m", "research_cli.mcp_server", "--root",
                           str(PROJECT / "research-workspaces")]
    module = Path(importlib.util.find_spec("research_cli").origin)
    assert module.is_relative_to(PROJECT / ".mcp-venv" / "Lib" / "site-packages")
    source_matches = {}
    for source in sorted((PROJECT / "research_cli").glob("*.py")):
        installed = module.parent / source.name
        source_matches[source.name] = source.read_bytes() == installed.read_bytes()
    assert all(source_matches.values()), "Installed source differs from current source"
    workspace = "installation-check-" + uuid.uuid4().hex
    transcript = []
    parameters = StdioServerParameters(command=own["command"], args=own["args"],
                                       cwd=PROJECT.parent)
    async with Client(parameters, read_timeout_seconds=30) as client:
        tools = await client.list_tools()
        names = sorted(tool.name for tool in tools.tools)
        assert names == sorted(tool['name'] for tool in tool_descriptions())

        async def call(name, **arguments):
            arguments["workspace"] = workspace
            result = await client.call_tool(name, arguments)
            envelope = result.structured_content
            assert json.loads(result.content[0].text) == envelope
            assert envelope["ok"] and not result.is_error, envelope
            transcript.append({"tool": name, "arguments": arguments, "result": envelope})
            return envelope["data"]

        await call("research_help")
        initialized = await call("research_init")
        assert "owner_key_path" not in initialized and "internal_key_path" not in initialized
        goal = await call("research_goal", title="MCP 설치 확인",
                          description="Development-only installed launcher probe; no experiment")
        await call("research_hypothesis", goal=goal["id"],
                   statement="설치된 서버에서 입력과 영속 상태를 연결할 수 있다")
        await call("research_status", goal=goal["id"])
        await call("research_memory", query="설치 확인", limit=5)
    assert CONFIG.read_bytes() == original_config, "Codex configuration changed during this read-only probe"
    wheel = PROJECT / "validation" / "wheels" / ("research_state_cli-" + VERSION + "-py3-none-any.whl")
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "version": metadata.version("research-state-cli"),
        "mcp_sdk": metadata.version("mcp"),
        "codex_server": "research_state", "codex_registered": True,
        "launcher": own, "configuration_unchanged_during_probe": True,
        "actual_stdio_transport": True, "isolated_installed_module": str(module),
        "tested_outside_source_directory": True, "tool_count": len(names), "tools": names,
        "installed_source_matches": source_matches,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "workspace": workspace, "model_calls": False, "experiment_launched": False,
        "core_runtime_dependencies": [], "transcript": transcript,
    }
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("version", "codex_registered", "tool_count",
                     "actual_stdio_transport", "model_calls", "experiment_launched")}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
