"""Optional stdio MCP interface to the same research-state operations as the CLI."""
import argparse
import json
import logging
import sys
from typing import Any, Literal

from . import __version__


def create_server(root):
    """Build the optional SDK server; importing the core CLI never loads this SDK."""
    from mcp.server import MCPServer
    from mcp_types import CallToolResult, TextContent, ToolAnnotations
    from .mcp_bridge import Bridge

    bridge = Bridge(root)
    server = MCPServer(
        name="research-state",
        version=__version__,
        instructions=(
            "Manage research state through these tools. Workspaces are relative to the configured root. "
            "The external agent chooses hypotheses, writes experiment code, and calls models. "
            "Start with research_help and research_status; use research_memory before proposing experiments. "
            "Register conditions before execution. Execution success, verification success, and adoption are separate. "
            "Owner validator registration remains a local CLI operation. An unknown run must be recovered or "
            "investigated; repeating a run request does not authorize a second execution. Laya inference is external."
        ),
        log_level="WARNING",
        subscriptions=False,
    )
    read = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    write = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                            idempotent_hint=False, open_world_hint=False)
    execution = ToolAnnotations(read_only_hint=False, idempotent_hint=False,
                                open_world_hint=True)

    def call(operation, workspace, **params):
        envelope = bridge.call(operation, workspace=workspace, **params)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(envelope, ensure_ascii=False,
                                                            allow_nan=False, separators=(",", ":")))],
            structured_content=envelope,
            is_error=not envelope.get("ok", False),
        )

    # The SDK runs synchronous handlers in worker threads. A long local execution
    # therefore does not block unrelated status requests on the stdio event loop.
    @server.tool(annotations=read)
    def research_help(topic: Literal["register", "laya", "goal"] | None = None,
                      workspace: str = "default") -> CallToolResult:
        """Read command help or a public preregistration/Laya JSON example."""
        return call("help", workspace, topic=topic)

    @server.tool(annotations=write)
    def research_init(workspace: str = "default") -> CallToolResult:
        """Initialize a research workspace; private local capability contents are not returned."""
        return call("init", workspace)

    @server.tool(annotations=write)
    def research_goal(title: str, description: str = "",
                      brief: dict[str, Any] = {}, request_key: str | None = None,
                      expect: int | None = None,
                      workspace: str = "default") -> CallToolResult:
        """Record an externally chosen research objective."""
        return call("goal", workspace, title=title, description=description, brief=brief or {}, request_key=request_key, expect=expect)

    @server.tool(annotations=read)
    def research_goal_show(goal: str, limit: int = 20, offset: int = 0,
                           workspace: str = "default") -> CallToolResult:
        """Read the goal's current version, lifecycle, paginated history and external resource observations."""
        return call("goal_show", workspace, goal=goal, limit=limit, offset=offset)

    @server.tool(annotations=write)
    def research_goal_amend(goal: str, brief: dict[str, Any], reason: str,
                            change_kind: Literal["meaning", "scope", "plan"], request_key: str,
                            expect: int, title: str | None = None, description: str | None = None,
                            workspace: str = "default") -> CallToolResult:
        """Append an explicit meaning/scope/plan version; frozen experiment criteria and original goal versions remain immutable."""
        return call("goal_amend", workspace, goal=goal, brief=brief, reason=reason, change_kind=change_kind,
                    request_key=request_key, expect=expect, title=title, description=description)

    @server.tool(annotations=write)
    def research_goal_close(goal: str, state: Literal["completed", "paused", "cancelled"], reason: str,
                            results: list[str], incomplete: list[str], request_key: str, expect: int,
                            workspace: str = "default") -> CallToolResult:
        """Record a research completion/pause/cancellation report. It does not certify science or stop any worker."""
        return call("goal_close", workspace, goal=goal, state=state, reason=reason, results=results,
                    incomplete=incomplete, request_key=request_key, expect=expect)

    @server.tool(annotations=write)
    def research_goal_resume(goal: str, reason: str, request_key: str, expect: int,
                             workspace: str = "default") -> CallToolResult:
        """Reactivate the same goal; never create a replacement goal or launch an experiment."""
        return call("goal_resume", workspace, goal=goal, reason=reason, request_key=request_key, expect=expect)

    @server.tool(annotations=write)
    def research_resource(goal: str, observation: dict[str, Any], request_key: str,
                          expect: int | None = None, workspace: str = "default") -> CallToolResult:
        """Append a sourced external cost/token observation, with unknown gaps and no independent certification."""
        return call("resource", workspace, goal=goal, observation=observation, request_key=request_key, expect=expect)

    @server.tool(annotations=read)
    def research_resource_show(goal: str, limit: int = 20, offset: int = 0,
                               workspace: str = "default") -> CallToolResult:
        """Read paginated original observations and currency-separated observed subtotals; full research cost remains unknown."""
        return call("resource_show", workspace, goal=goal, limit=limit, offset=offset)

    @server.tool(annotations=write)
    def research_hypothesis(goal: str, statement: str, expect: int | None = None,
                            workspace: str = "default") -> CallToolResult:
        """Record a proposed hypothesis. Optional expect rejects a stale workspace revision."""
        return call("hypothesis", workspace, goal=goal, statement=statement, expect=expect)

    @server.tool(annotations=write)
    def research_register(goal: str, spec: dict[str, Any], request_key: str,
                          expect: int | None = None, workspace: str = "default") -> CallToolResult:
        """Freeze conditions and success criteria before execution. Use research_help(topic='register') for spec.

        Criteria cannot be overwritten after registration. A changed experiment needs a new registration.
        A local owner must first register the fixed validator using the CLI.
        """
        return call("register", workspace, goal=goal, input=spec, request_key=request_key, expect=expect)

    @server.tool(annotations=read)
    def research_status(goal: str | None = None, limit: int = 20, offset: int = 0,
                        workspace: str = "default") -> CallToolResult:
        """Read paginated state, currently allowed operations, and missing evidence without scientific ranking."""
        return call("status", workspace, goal=goal, limit=limit, offset=offset)

    @server.tool(annotations=read)
    def research_memory(query: str = "", outcome: Literal["success", "failure", "inconclusive"] | None = None,
                        verification: Literal["pending", "passed", "failed", "inconclusive"] | None = None,
                        limit: int = 20, offset: int = 0, workspace: str = "default") -> CallToolResult:
        """Search paginated research summaries by literal substring and outcome; claim verification is explicit."""
        return call("memory", workspace, query=query, outcome=outcome, verification=verification,
                    limit=limit, offset=offset)

    @server.tool(annotations=read)
    def research_show(registration: str, workspace: str = "default") -> CallToolResult:
        """Read a complete registration, original evidence links, current integrity, and verification/decision states."""
        return call("show", workspace, registration=registration)

    @server.tool(annotations=execution)
    def research_run(registration: str, request_key: str, expect: int | None = None,
                     full: bool = False, workspace: str = "default") -> CallToolResult:
        """Execute a preregistered local experiment once it is claimed; repeated requests reuse known state.

        Unknown execution is not automatically rerun. This does not guarantee exactly-once external side effects.
        Default output summarizes evidence; full includes original execution receipts and details.
        """
        return call("run", workspace, registration=registration, request_key=request_key, expect=expect, full=full)

    @server.tool(annotations=write)
    def research_recover(registration: str, full: bool = False,
                         workspace: str = "default") -> CallToolResult:
        """Collect a surviving worker's receipt after interruption, or report unknown; never launch a replacement run."""
        return call("recover", workspace, registration=registration, full=full)

    @server.tool(annotations=execution)
    def research_verify(registration: str, full: bool = False,
                        workspace: str = "default") -> CallToolResult:
        """Run the owner's frozen validator on actual evidence and registered criteria; agent numbers cannot certify success."""
        return call("verify", workspace, registration=registration, full=full)

    @server.tool(annotations=write)
    def research_decide(registration: str, decision: Literal["adopted", "rejected", "inconclusive"],
                        reason: str, expect: int | None = None,
                        workspace: str = "default") -> CallToolResult:
        """Record the external agent's decision; adoption requires successful execution and valid independently verified evidence."""
        return call("decide", workspace, registration=registration, decision=decision, reason=reason, expect=expect)

    @server.tool(annotations=write)
    def research_evidence(registration: str, kind: Literal["measured", "literature", "inference", "proposal"],
                          claim: str, path: str | None = None, expect: int | None = None,
                          workspace: str = "default") -> CallToolResult:
        """Append an unverified claim and optional evidence file relative to the workspace; this never certifies an experiment."""
        return call("evidence", workspace, registration=registration, kind=kind, claim=claim, path=path, expect=expect)

    @server.tool(annotations=write)
    def research_export(output: str, workspace: str = "default") -> CallToolResult:
        """Create a consistent, hashed archive at a relative workspace path; existing output is not overwritten."""
        return call("export", workspace, output=output)

    @server.tool(annotations=write)
    def research_restore(input: str, workspace: str = "default") -> CallToolResult:
        """Restore an archive under the configured root into an empty workspace; restoration never executes an experiment."""
        return call("restore", workspace, input=input)

    @server.tool(annotations=read)
    def research_laya_prepare(payload: dict[str, Any], workspace: str = "default") -> CallToolResult:
        """Return candidates, conditions, evidence, and a bound Laya request. The external agent saves the digest and runs Laya."""
        return call("laya_prepare", workspace, input=payload)

    @server.tool(annotations=read)
    def research_laya_resolve(bundle: dict[str, Any], response: dict[str, Any], expected_sha256: str,
                              workspace: str = "default") -> CallToolResult:
        """Bind an external Laya response to candidate IDs and return an unverified proposal; no model call or automatic adoption."""
        return call("laya_resolve", workspace, input=bundle, response=response, expected_sha256=expected_sha256)

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="research-state-mcp",
                                     description="Optional stdio MCP wrapper for the research-state CLI")
    parser.add_argument("--root", required=True, help="Dedicated directory containing relative research workspaces")
    args = parser.parse_args(argv)
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        server = create_server(args.root)
    except ImportError:
        print("research-state MCP requires its optional SDK. Install research-state-cli[mcp] "
              "in the server's Python environment.", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print("Cannot start research-state MCP: " + str(exc), file=sys.stderr)
        return 2
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
