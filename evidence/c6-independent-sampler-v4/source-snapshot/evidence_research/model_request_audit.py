"""Independent audit of the actual Codex request settings, never provider prose.

Only the explicitly supported host command contract is accepted. Matching a
public model ID does not assert a stable or visible server weight version.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def audit_request_settings(request: dict, result: dict, *, model_id: str,
                           resource_envelope: dict, folder: Path, arm_output: Path) -> dict:
    folder, arm_output = Path(folder).resolve(), Path(arm_output).resolve()
    if "reasoning_effort" not in resource_envelope:
        raise ValueError("registered reasoning effort must be explicit, including null")
    effort = resource_envelope["reasoning_effort"]
    if effort is not None and effort not in ("none","minimal","low","medium","high","xhigh","max","ultra"):
        raise ValueError("unsupported registered reasoning effort")
    if request.get("model") != model_id or result.get("model") != model_id or request.get("reasoning_effort") != effort:
        raise ValueError("actual request model/reasoning effort differs from registered resources")
    identity_keys = ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")
    if any(key not in request for key in identity_keys):
        raise ValueError("matched evaluation requires full prompt and provider-source lineage")
    if not isinstance(request["prompt"],str) or not isinstance(request["full_prompt"],str) or not request["full_prompt"].endswith(request["prompt"]):
        raise ValueError("full prompt does not contain the exact submitted task prompt")
    source = request["provider_source_sha256"]
    if not isinstance(source,str) or len(source)!=64 or any(c not in "0123456789abcdef" for c in source):
        raise ValueError("invalid provider source hash")
    current_source=Path(__file__).with_name("model.py")
    if hashlib.sha256(current_source.read_bytes()).hexdigest()!=source:
        raise ValueError("request provider source differs from the executing frozen provider")
    from .model import CodexProvider
    if request["full_prompt"] != CodexProvider.guard + request["prompt"]:
        raise ValueError("actual full prompt differs from the frozen proposal-only guard")
    identity={key:request[key] for key in identity_keys}
    fingerprint=hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    if request.get("fingerprint")!=fingerprint or result.get("fingerprint")!=fingerprint:
        raise ValueError("actual request fingerprint differs from raw matched model evidence")
    command=request.get("command")
    if not isinstance(command,list) or any(not isinstance(v,str) for v in command) or len(command)<3 or command[1]!="exec" or command[-1]!="-":
        raise ValueError("actual model CLI command contract invalid")
    required_flags={"--ignore-user-config","--ephemeral","--skip-git-repo-check","--json"}
    options={"--sandbox":"read-only","--model":model_id}
    seen,configs,values=set(),[],{}
    i=2
    while i<len(command)-1:
        token=command[i]
        if token in required_flags:
            if token in seen: raise ValueError("duplicate CLI isolation flag")
            seen.add(token);i+=1
        elif token in ("--sandbox","--model","--cd","--output-last-message"):
            if token in values or i+1>=len(command)-1: raise ValueError("duplicate or missing CLI option")
            values[token]=command[i+1];i+=2
        elif token=="-c":
            if i+1>=len(command)-1: raise ValueError("missing CLI configuration value")
            configs.append(command[i+1]);i+=2
        else: raise ValueError("unregistered actual model CLI setting")
    if seen!=required_flags or any(values.get(k)!=v for k,v in options.items()):
        raise ValueError("actual CLI model or isolation settings differ from shared contract")
    expected_configs=['approval_policy="never"']
    if effort is not None: expected_configs.append(f'model_reasoning_effort="{effort}"')
    if sorted(configs)!=sorted(expected_configs):
        raise ValueError("actual CLI reasoning effort/configuration differs from registered resources")
    cwd=Path(values.get("--cd","")).resolve()
    output=Path(values.get("--output-last-message","")).resolve()
    if not cwd.is_relative_to(arm_output) or cwd.name!="public_model_cwd" or cwd.is_symlink() or output!=folder / "response.txt":
        raise ValueError("actual CLI public working directory or response path differs from registered boundary")
    return {"valid":True,"model_id":model_id,"reasoning_effort":effort,"request_fingerprint":fingerprint,
            "provider_source_sha256":source,"command_contract":"ignored user config; ephemeral; read-only sandbox; no approval; public cwd; JSON; exact model/effort; stdin prompt",
            "limits":"Records requested public model/settings; unexposed server weight versions and sampling seed are not asserted."}
