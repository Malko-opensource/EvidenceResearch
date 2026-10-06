"""Model-free WebMCP tool descriptions and validation for the shared CLI bridge."""

from copy import deepcopy

from .core import ResearchError, canonical


def _nullable(schema, default=None):
    return {"anyOf": [schema, {"type": "null"}], "default": default}


_STRING = {"type": "string"}
_OBJECT = {"type": "object", "additionalProperties": True}
_EXPECT = _nullable({"type": "integer"})
_WORKSPACE = {"type": "string", "default": "default",
              "description": "Relative research workspace beneath the configured root."}
_READ = {"readOnlyHint": True, "openWorldHint": False}
_WRITE = {"readOnlyHint": False, "destructiveHint": False,
          "idempotentHint": False, "openWorldHint": False}
_EXECUTION = {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True}


def _tool(operation, description, properties=None, required=(), annotations=_WRITE):
    fields = dict(properties or {}) | {"workspace": _WORKSPACE}
    schema = {"type": "object", "properties": fields, "additionalProperties": False}
    if required:
        schema["required"] = list(required)
    return {"name": "research_" + operation, "description": description,
            "inputSchema": schema, "annotations": annotations}


TOOLS = [
    _tool("help", "Read command help or a public preregistration/Laya JSON example.",
          {"topic": _nullable({"type": "string", "enum": ["register", "laya", "goal"]})}, annotations=_READ),
    _tool("init", "Initialize a research workspace; private local capability contents are not returned."),
    _tool("goal", "Record an externally chosen research objective.",
          {"title": _STRING, "description": {"type": "string", "default": ""},
           "brief": {"type": "object", "additionalProperties": True, "default": {}},
           "request_key": _nullable(_STRING), "expect": _EXPECT}, ("title",)),
    _tool("goal_show", "Read the current goal and immutable brief/lifecycle history with paginated source records.",
          {"goal": _STRING, "limit": {"type": "integer", "default": 20}, "offset": {"type": "integer", "default": 0}}, ("goal",), _READ),
    _tool("goal_amend", "Append an explicit goal meaning/scope/plan version; frozen experiments retain their original version and criteria. An identical request key reuses its result.",
          {"goal": _STRING, "brief": _OBJECT, "reason": _STRING,
           "change_kind": {"type": "string", "enum": ["meaning", "scope", "plan"]},
           "request_key": _STRING, "expect": {"type": "integer"},
           "title": _nullable(_STRING), "description": _nullable(_STRING)},
          ("goal", "brief", "reason", "change_kind", "request_key", "expect")),
    _tool("goal_close", "Record completed/paused/cancelled research with reason, obtained results and incomplete scope. This external report is not scientific verification and never cancels a worker.",
          {"goal": _STRING, "state": {"type": "string", "enum": ["completed", "paused", "cancelled"]},
           "reason": _STRING, "results": {"type": "array", "items": _STRING},
           "incomplete": {"type": "array", "items": _STRING}, "request_key": _STRING, "expect": {"type": "integer"}},
          ("goal", "state", "reason", "results", "incomplete", "request_key", "expect")),
    _tool("goal_resume", "Resume the same goal after closure or legacy unknown lifecycle; no experiment is duplicated or started.",
          {"goal": _STRING, "reason": _STRING, "request_key": _STRING, "expect": {"type": "integer"}},
          ("goal", "reason", "request_key", "expect")),
    _tool("resource", "Append a sourced external cost/token observation. Observed subtotals never imply complete cost or independent verification; repeated source references are not double counted.",
          {"goal": _STRING, "observation": _OBJECT, "request_key": _STRING, "expect": _EXPECT},
          ("goal", "observation", "request_key")),
    _tool("resource_show", "Read paginated external resource observations and currency-separated observed subtotals with unknown coverage.",
          {"goal": _STRING, "limit": {"type": "integer", "default": 20}, "offset": {"type": "integer", "default": 0}}, ("goal",), _READ),
    _tool("hypothesis", "Record a proposed hypothesis. Optional expect rejects a stale workspace revision.",
          {"goal": _STRING, "statement": _STRING, "expect": _EXPECT}, ("goal", "statement")),
    _tool("register", "Freeze conditions and success criteria before execution. A local owner first freezes the validator through the CLI. Changed conditions require a new registration.",
          {"goal": _STRING, "spec": _OBJECT, "request_key": _STRING, "expect": _EXPECT},
          ("goal", "spec", "request_key")),
    _tool("status", "Read paginated state, currently allowed operations, and missing evidence without scientific ranking.",
          {"goal": _nullable(_STRING), "limit": {"type": "integer", "default": 20},
           "offset": {"type": "integer", "default": 0}}, annotations=_READ),
    _tool("memory", "Search paginated research summaries; record existence and claim verification are separate.",
          {"query": {"type": "string", "default": ""},
           "outcome": _nullable({"type": "string", "enum": ["success", "failure", "inconclusive"]}),
           "verification": _nullable({"type": "string", "enum": ["pending", "passed", "failed", "inconclusive"]}),
           "limit": {"type": "integer", "default": 20}, "offset": {"type": "integer", "default": 0}},
          annotations=_READ),
    _tool("show", "Read a complete registration, original evidence links, current integrity, and separate verification/decision states.",
          {"registration": _STRING}, ("registration",), _READ),
    _tool("run", "Execute a preregistered local experiment after claiming it. Repeated requests reuse known state; unknown execution is not automatically rerun. External side effects are not guaranteed exactly once.",
          {"registration": _STRING, "request_key": _STRING, "expect": _EXPECT,
           "full": {"type": "boolean", "default": False}}, ("registration", "request_key"), _EXECUTION),
    _tool("recover", "Collect a surviving worker receipt after interruption or report unknown; never launch a replacement run.",
          {"registration": _STRING, "full": {"type": "boolean", "default": False}}, ("registration",)),
    _tool("verify", "Run the owner's frozen validator against actual evidence and registered criteria. Agent numbers cannot certify success.",
          {"registration": _STRING, "full": {"type": "boolean", "default": False}}, ("registration",), _EXECUTION),
    _tool("decide", "Record an external decision. Adoption requires successful execution and valid independently verified evidence.",
          {"registration": _STRING, "decision": {"type": "string", "enum": ["adopted", "rejected", "inconclusive"]},
           "reason": _STRING, "expect": _EXPECT}, ("registration", "decision", "reason")),
    _tool("evidence", "Append an unverified claim and optional evidence file. This never certifies an experiment.",
          {"registration": _STRING, "kind": {"type": "string", "enum": ["measured", "literature", "inference", "proposal"]},
           "claim": _STRING, "path": _nullable(_STRING), "expect": _EXPECT},
          ("registration", "kind", "claim")),
    _tool("export", "Create a consistent hashed archive beneath the configured root. Existing output is not overwritten.",
          {"output": _STRING}, ("output",)),
    _tool("restore", "Restore an archive beneath the root into an empty workspace; restoration never executes an experiment.",
          {"input": _STRING}, ("input",)),
    _tool("laya_prepare", "Bind candidates and current evidence to an external Laya request. Inference remains external.",
          {"payload": _OBJECT}, ("payload",), _READ),
    _tool("laya_resolve", "Map an external Laya response to a bound, unverified proposal; no automatic scientific choice or adoption.",
          {"bundle": _OBJECT, "response": _OBJECT, "expected_sha256": _STRING},
          ("bundle", "response", "expected_sha256"), _READ),
]
_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def tool_descriptions():
    """Return public, independently mutable JSON descriptions without any SDK."""
    return deepcopy(TOOLS)


def _valid(value, schema):
    if "anyOf" in schema:
        return any(_valid(value, option) for option in schema["anyOf"])
    kind = schema.get("type")
    match = {"string": isinstance(value, str),
             "integer": isinstance(value, int) and not isinstance(value, bool),
             "boolean": isinstance(value, bool), "object": isinstance(value, dict),
             "array": isinstance(value, list),
             "null": value is None}.get(kind, True)
    return match and ("enum" not in schema or value in schema["enum"])


def call_tool(bridge, name, arguments):
    """Validate the public contract, then enter the existing shared transition path."""
    if not isinstance(name, str) or name not in _BY_NAME or not isinstance(arguments, dict):
        raise ResearchError("INVALID_INPUT", "Expected a known research tool and object arguments")
    canonical(arguments)  # Also reject non-finite or non-JSON nested values.
    schema = _BY_NAME[name]["inputSchema"]
    fields = schema["properties"]
    if set(arguments) - set(fields):
        raise ResearchError("INVALID_INPUT", "Unknown tool argument", {"tool": name})
    missing = set(schema.get("required", [])) - set(arguments)
    if missing:
        raise ResearchError("INVALID_INPUT", "Required tool arguments are missing", {"fields": sorted(missing)})
    for field, value in arguments.items():
        if not _valid(value, fields[field]):
            raise ResearchError("INVALID_INPUT", "Tool argument has an invalid type or value", {"field": field})
    values = {field: deepcopy(spec["default"]) for field, spec in fields.items() if "default" in spec}
    values.update(arguments)
    workspace = values.pop("workspace")
    operation = name.removeprefix("research_")
    rename = {"register": "spec", "laya_prepare": "payload", "laya_resolve": "bundle"}.get(operation)
    if rename:
        values["input"] = values.pop(rename)
    return bridge.call(operation, workspace=workspace, **values)
