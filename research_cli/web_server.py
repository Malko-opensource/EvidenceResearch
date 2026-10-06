"""Loopback HTTP channel for the research CLI and native browser WebMCP page."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import math
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import webbrowser

from . import __version__
from .core import ResearchError, Store
from .mcp_bridge import Bridge
from .web_tools import call_tool, tool_descriptions


_MAX_BODY = 1024 * 1024
_MAX_PREVIEW = 256 * 1024
_ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
           "/index.html": ("index.html", "text/html; charset=utf-8"),
           "/app.js": ("app.js", "text/javascript; charset=utf-8"),
           "/view_model.js": ("view_model.js", "text/javascript; charset=utf-8"),
           "/styles.css": ("styles.css", "text/css; charset=utf-8")}
_LOG = logging.getLogger(__name__)


def _error(code, message, details=None):
    return {"ok": False, "error": {"code": code, "message": message, "details": details or {}}}


def _query(query, allowed):
    values = parse_qs(query, keep_blank_values=True, strict_parsing=True)
    if set(values) - set(allowed) or any(len(items) != 1 for items in values.values()):
        raise ResearchError("INVALID_INPUT", "Unknown or repeated query parameter")
    return {key: items[0] for key, items in values.items()}


def _page(parameters):
    try:
        limit, offset = int(parameters.get("limit", "20")), int(parameters.get("offset", "0"))
    except ValueError as exc:
        raise ResearchError("INVALID_INPUT", "Page limit and offset must be integers") from exc
    if not 1 <= limit <= 100 or offset < 0:
        raise ResearchError("INVALID_INPUT", "Page limit must be 1..100 and offset nonnegative")
    return limit, offset


def _scoped_workspace(bridge, name):
    path = bridge.workspace(name)
    metadata = (path / ".research").resolve()
    database = (metadata / "state.sqlite3").resolve()
    if not metadata.is_relative_to(path) or not database.is_relative_to(metadata):
        raise ResearchError("PERMISSION_DENIED", "Workspace metadata link leaves its storage directory")
    return path


def _private_file(path):
    parts = [part.casefold() for part in Path(path).parts]
    name = Path(path).name.casefold()
    return ".research" in parts and (name in ("owner.key", "internal.key") or name.startswith("state.sqlite3"))


class _WebBridge(Bridge):
    def call(self, operation, workspace="default", **parameters):
        try:
            path = _scoped_workspace(self, workspace)
            source = parameters.get("path") if operation == "evidence" else None
            if source is not None and _private_file(self._file(source, path)):
                raise ResearchError("PERMISSION_DENIED", "Private storage keys and databases are not web evidence inputs")
        except ResearchError as exc:
            return _error(exc.code, str(exc), exc.details)
        return super().call(operation, workspace=workspace, **parameters)


def _read_database(store, callback):
    connection = sqlite3.connect(store.db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("BEGIN")
        return callback(connection)
    finally:
        connection.close()


def _workspaces(bridge, limit, offset):
    items = []
    if bridge.root.is_dir():
        for directory, children, _ in os.walk(bridge.root, followlinks=False):
            path = Path(directory)
            ancestors = {parent.resolve() for parent in (path, *path.parents)}
            children[:] = sorted(name for name in children
                                 if name.casefold() != ".research" and not (path / name).is_symlink()
                                 and (path / name).resolve().is_relative_to(bridge.root)
                                 and (path / name).resolve() not in ancestors)
            if path == bridge.root or not (path / ".research/state.sqlite3").is_file():
                continue
            name = path.relative_to(bridge.root).as_posix()
            try:
                store = Store(_scoped_workspace(bridge, name))
                revision = _read_database(store, lambda c: int(c.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]))
            except (ResearchError, OSError, ValueError, TypeError, sqlite3.Error):
                continue  # An incomplete or foreign directory is not an initialized store.
            items.append({"name": name, "revision": revision})
    items.sort(key=lambda item: item["name"])
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}


def _goal_report(store, goal_id, revision, limit, offset, registration=None):
    """Read an explicitly scoped goal report; never infer lifecycle or total spend."""
    observed_at = time.time()
    def collect(connection):
        rows = [dict(row) for row in connection.execute(
            "SELECT r.*,p.hypothesis_id,p.spec FROM runs r JOIN registrations p "
            "ON p.id=r.registration_id WHERE p.goal_id=? ORDER BY r.created,r.id", (goal_id,))]
        registration_rows = connection.execute(
            "SELECT id FROM registrations WHERE goal_id=? ORDER BY created DESC,id LIMIT ? OFFSET ?",
            (goal_id, min(limit, 6), offset)).fetchall()
        ids = [row['id'] for row in registration_rows]
        if registration and registration not in ids:
            ids = [registration, *ids][:min(limit, 6)]
        total = connection.execute("SELECT COUNT(*) FROM registrations WHERE goal_id=?", (goal_id,)).fetchone()[0]
        current_revision = int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
        observations = [dict(row) for row in connection.execute(
            "SELECT o.record,p.hypothesis_id FROM resource_observations o LEFT JOIN registrations p "
            "ON p.id=o.registration_id WHERE o.goal_id=?", (goal_id,))]
        hypothesis_ids = [row[0] for row in connection.execute(
            'SELECT DISTINCT hypothesis_id FROM registrations WHERE goal_id=? ORDER BY hypothesis_id', (goal_id,))]
        request_counts = dict(connection.execute(
            "SELECT r.id,COUNT(q.key) FROM runs r JOIN registrations p ON p.id=r.registration_id "
            "LEFT JOIN requests q ON q.scope='run' AND q.target=r.id WHERE p.goal_id=? GROUP BY r.id", (goal_id,)))
        return rows, ids, total, current_revision, observations, hypothesis_ids, request_counts
    rows, ids, total, query_revision, observations, hypothesis_ids, request_counts = _read_database(store, collect)
    values, runs = [], []
    branches = {identifier: {'hypothesis_id':identifier, 'runs_total':0, 'wall_seconds':0,
                            'known':0, 'unknown':0, 'run_ids':[]} for identifier in hypothesis_ids}
    for row in rows:
        resources, spec = json.loads(row['resources']), json.loads(row.pop('spec'))
        value = resources.get('wall_seconds')
        known = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
        if known:
            values.append(value)
        run = {**row, 'resources': resources, 'source_version': spec.get('source_version'),
               'ref': {'registration': row['registration_id'], 'run': row['id'], 'revision': query_revision}}
        runs.append(run)
        branch = branches.setdefault(row['hypothesis_id'], {'hypothesis_id': row['hypothesis_id'],
                   'runs_total': 0, 'wall_seconds': 0, 'known': 0, 'unknown': 0, 'run_ids': []})
        branch['runs_total'] += 1
        branch['run_ids'].append(row['id'])
        branch['known' if known else 'unknown'] += 1
        if known:
            branch['wall_seconds'] += value
    for branch in branches.values():
        if not branch['known']:
            branch['wall_seconds'] = None
        branch['run_ids_total'] = len(branch['run_ids'])
        branch['run_ids'] = branch['run_ids'][-6:]
        costs, cost_known, cost_unknown = {}, 0, 0
        for observation in observations:
            if observation['hypothesis_id'] != branch['hypothesis_id']:
                continue
            cost = json.loads(observation['record'])['cost']
            if cost['status'] == 'known':
                costs[cost['currency']] = costs.get(cost['currency'], 0) + cost['amount']
                cost_known += 1
            else:
                cost_unknown += 1
        branch['resources'] = {'cost_by_currency': [{'currency': key, 'amount': value} for key, value in sorted(costs.items())],
                               'known_count': cost_known, 'unknown_count': cost_unknown,
                               'scope': 'recorded_external_observations_linked_to_branch', 'total_cost_status': 'unknown'}
    goal_detail = store.goal_show(goal_id, limit=min(limit, 20), offset=0)
    resources = store.resource_summary(goal_id)
    resource_page = store.resource_show(goal_id, limit=min(limit, 20), offset=0)
    records = [store.show(identifier) for identifier in ids]
    error_groups = {}
    for row in rows:
        if row['state'] == 'failed':
            reason = row['reason'] or None
            group = error_groups.setdefault(reason, {'reason':reason,'distinct_runs':0,'run_ids':[]})
            group['distinct_runs'] += 1
            if len(group['run_ids']) < 6:
                group['run_ids'].append(row['id'])
    execution_audit = {'scope':'all_selected_goal_runs', 'request_keys_total':sum(request_counts.values()),
                       'replay_attempt_count':None, 'requests_received_count':None,
                       'replay_coverage':'identical-key retry attempts are not persisted; key mappings are not a call count',
                       'per_run':[{'run':row['id'],'registration':row['registration_id'],'state':row['state'],
                                   'request_key_count':request_counts.get(row['id'],0),
                                   'ref':{'field':'requests.target','run':row['id'],'registration':row['registration_id'],'revision':query_revision}}
                                  for row in rows[-min(limit,100):]],
                       'error_groups':list(error_groups.values())[:6], 'error_groups_total':len(error_groups),
                       'error_scope':'execution failures only; failed scientific criteria are not execution errors',
                       'unresolved_runs':[{'run':row['id'],'registration':row['registration_id'],'state':row['state'],'reason':row['reason'],
                                           'allowed_action':'recover'} for row in rows if row['state'] in ('running','unknown')][:100],
                       'unresolved_total':sum(row['state'] in ('running','unknown') for row in rows),
                       'ref':{'goal':goal_id,'field':'runs/requests','revision':query_revision}}
    versions = [revision, query_revision, goal_detail.get('revision'), resources.get('revision'), resource_page.get('revision'),
                *[record['revision'] for record in records]]
    return {'goal': goal_detail['goal'], 'observed_at': observed_at,
            'scope': {'goal_id': goal_id, 'goal_version': goal_detail['goal']['version'],
                      'registrations_total': total, 'runs_total': len(rows), 'kind': 'selected_goal_all_runs'},
            'totals': {'run_wall_seconds': {'value': sum(values) if values else None,
                       'known': len(values), 'unknown': len(rows) - len(values), 'unit': 'seconds',
                       'kind': 'sum_of_observed_execution_durations'}},
            'resources': resources, 'branches': list(branches.values())[-6:], 'branches_total': len(branches),
            'resource_observations': resource_page['items'], 'resource_observations_total': resource_page['total'],
            'resource_observations_limit': resource_page['limit'],
            'execution_audit':execution_audit,
            'runs': runs[-min(limit, 100):], 'runs_total': len(rows), 'runs_limit': min(limit, 100),
            'records': records, 'records_total': total, 'records_limit': min(limit, 6), 'records_offset': offset,
            'revision': query_revision, 'consistent': len(set(value for value in versions if value is not None)) == 1,
            'refs': [{'goal': goal_id, 'goal_version': goal_detail['goal']['version'], 'field': 'goals', 'revision': query_revision},
                     {'goal': goal_id, 'field': 'runs.resources', 'scope': 'all_goal_runs', 'revision': query_revision}]}


def _snapshot(bridge, name, limit, offset, registration=None, goal=None):
    store = Store(_scoped_workspace(bridge, name))
    if registration:
        selected_record = store.show(registration)
        linked_goal = selected_record['registration']['goal_id']
        if goal and goal != linked_goal:
            raise ResearchError('INVALID_INPUT', 'Selected registration does not belong to selected goal')
        goal = linked_goal
    status = bridge.call("status", workspace=name, goal=goal, limit=limit, offset=offset)
    if not status["ok"]:
        return status
    revision = status["data"]["revision"]
    if not goal and status['data']['goals']:
        goal = status['data']['goals'][0]['id']
    targets = None
    if registration:
        record = selected_record
        targets = [registration, record["registration"]["goal_id"],
                   record["registration"]["hypothesis_id"],
                   record["registration"]["spec"]["validator"]]
        if record["run"]:
            targets.append(record["run"]["id"])

    def recent(connection):
        # A concurrent CLI write can advance after status. Keep this response's
        # events at or before its status revision rather than mixing snapshots.
        where, parameters = "revision<=?", [revision]
        if targets:
            where += " AND (target IN (" + ",".join("?" for _ in targets) + ") OR target IN (SELECT id FROM resource_observations WHERE registration_id=?))"
            parameters.extend(targets)
            parameters.append(registration)
        elif goal:
            where += " AND (target=? OR target IN (SELECT id FROM hypotheses WHERE goal_id=?) OR target IN (SELECT id FROM registrations WHERE goal_id=?) OR target IN (SELECT r.id FROM runs r JOIN registrations p ON p.id=r.registration_id WHERE p.goal_id=?) OR target IN (SELECT id FROM resource_observations WHERE goal_id=?))"
            parameters.extend([goal] * 5)
        rows = connection.execute("SELECT id,revision,action,target,created FROM events WHERE " + where + " ORDER BY id DESC LIMIT 20", parameters).fetchall()
        count = connection.execute("SELECT COUNT(*) FROM events WHERE " + where, parameters).fetchone()[0]
        return [dict(row) for row in rows], count

    events, count = _read_database(store, recent)
    return {"ok": True, "data": {"status": status["data"], "events": events, "event_total": count,
                                 "event_scope": "selected_registration" if registration else ('selected_goal' if goal else "workspace"),
                                 "registration": registration,
                                 "report": _goal_report(store, goal, revision, limit, offset, registration) if goal else None}}


def _evidence(bridge, name, registration, evidence_id):
    if not registration or not evidence_id:
        raise ResearchError("INVALID_INPUT", "Registration and evidence IDs are required")
    store = Store(_scoped_workspace(bridge, name))
    record = store.show(registration)
    item = next((value for value in record["evidence"] if value["id"] == evidence_id), None)
    if item is None:
        raise ResearchError("NOT_FOUND", "Evidence is not linked to this registration")
    if not item.get("path"):
        raise ResearchError("EVIDENCE_MISSING", "This claim has no preserved source file")
    if item.get("original_path") and _private_file(item["original_path"]):
        raise ResearchError("PERMISSION_DENIED", "Private storage keys and databases are not web previews")
    path = (store.root / item["path"]).resolve()
    blobs = (store.metadata_dir / "evidence").resolve()
    if not blobs.is_relative_to(store.metadata_dir.resolve()) or not path.is_relative_to(blobs) or path.name != item.get("sha256"):
        raise ResearchError("EVIDENCE_TAMPERED", "Evidence reference is not a preserved content-addressed blob")
    try:
        with path.open("rb") as stream:
            digest = hashlib.sha256()
            preview, size = bytearray(), 0
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                if len(preview) < _MAX_PREVIEW:
                    preview.extend(chunk[:_MAX_PREVIEW - len(preview)])
    except OSError as exc:
        raise ResearchError("EVIDENCE_MISSING", "Preserved evidence cannot be read") from exc
    if digest.hexdigest() != item.get("sha256") or size != item.get("size"):
        raise ResearchError("EVIDENCE_TAMPERED", "Preserved evidence no longer matches its registered hash or size")
    return {"ok": True, "data": {"evidence": item, "text": bytes(preview).decode("utf-8", errors="replace"),
                                 "truncated": size > _MAX_PREVIEW, "bytes": size}}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


class _Handler(BaseHTTPRequestHandler):
    server_version = "ResearchStateWeb"
    sys_version = ""

    def log_message(self, format, *args):
        # Request paths may carry research identifiers. Never log headers, tokens,
        # query strings, body contents or private capability material.
        _LOG.debug("HTTP request completed")

    def _guard(self, mutation=False):
        expected = "%s:%s" % self.server.server_address
        if self.headers.get_all("Host", []) != [expected]:
            return _error("PERMISSION_DENIED", "Host must match this loopback server")
        origin = self.headers.get_all("Origin", [])
        if origin and origin != ["http://" + expected]:
            return _error("PERMISSION_DENIED", "Cross-origin access is not allowed")
        if any(value.strip().lower() == "cross-site" for value in self.headers.get_all("Sec-Fetch-Site", [])):
            return _error("PERMISSION_DENIED", "Cross-site access is not allowed")
        if mutation:
            tokens = self.headers.get_all("X-Research-Session", [])
            if len(tokens) != 1 or not hmac.compare_digest(tokens[0].encode("utf-8"), self.server.session_token.encode("ascii")):
                return _error("PERMISSION_DENIED", "A valid local page session is required")
        return None

    def _send(self, status, data, content_type="application/json; charset=utf-8", head=False):
        encoded = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if not head:
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass  # Disconnecting an HTTP client never relaunches a claim.

    def _get(self, head=False):
        denied = self._guard()
        if denied:
            self._send(403, denied, head=head)
            return
        try:
            url = urlsplit(self.path)
            if url.scheme or url.netloc or url.fragment:
                raise ResearchError("INVALID_INPUT", "Expected a relative request path")
            if url.path in _ASSETS:
                if url.query:
                    raise ResearchError("INVALID_INPUT", "Static files do not accept query parameters")
                asset, mime = _ASSETS[url.path]
                self._send(200, (Path(__file__).parent / "web" / asset).read_bytes(), mime, head)
                return
            if url.path == "/api/bootstrap":
                _query(url.query, ())
                result = {"ok": True, "data": {"version": __version__, "session_token": self.server.session_token,
                                               "tools": tool_descriptions()}}
            elif url.path == "/api/workspaces":
                parameters = _query(url.query, ("limit", "offset"))
                result = {"ok": True, "data": _workspaces(self.server.bridge, *_page(parameters))}
            elif url.path == "/api/snapshot":
                parameters = _query(url.query, ("workspace", "limit", "offset", "registration", "goal"))
                result = _snapshot(self.server.bridge, parameters.get("workspace", "default"), *_page(parameters),
                                   registration=parameters.get("registration"), goal=parameters.get("goal"))
            elif url.path == "/api/evidence":
                parameters = _query(url.query, ("workspace", "registration", "evidence"))
                result = _evidence(self.server.bridge, parameters.get("workspace", "default"),
                                   parameters.get("registration"), parameters.get("evidence"))
            else:
                self._send(404, _error("NOT_FOUND", "Unknown web endpoint"), head=head)
                return
            self._send(200, result, head=head)
        except ResearchError as exc:
            self._send(400 if exc.code == "INVALID_INPUT" else 200,
                       _error(exc.code, str(exc), exc.details), head=head)
        except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
            self._send(400, _error("INVALID_INPUT", str(exc)), head=head)

    def do_GET(self):
        self._get()

    def do_HEAD(self):
        self._get(head=True)

    def do_POST(self):
        denied = self._guard(mutation=True)
        if denied:
            # A bounded ordinary client may send its body after the headers.
            # Closing a Windows socket with unread bytes can discard the 403
            # response as a connection reset. Drain only a valid bounded body;
            # never parse it, resolve paths, or call a research transition.
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) == 1 and self.headers.get('Transfer-Encoding') is None:
                try:
                    length = int(lengths[0])
                    if 0 < length <= _MAX_BODY:
                        self.rfile.read(length)
                except (ValueError, OSError):
                    pass
            self._send(403, denied)
            return
        try:
            if self.path != "/api/call":
                self._send(404, _error("NOT_FOUND", "Unknown web endpoint"))
                return
            if self.headers.get("Transfer-Encoding") is not None or self.headers.get_all("Content-Length") is None or len(self.headers.get_all("Content-Length")) != 1:
                raise ResearchError("INVALID_INPUT", "A single bounded Content-Length is required")
            length = int(self.headers["Content-Length"])
            if not 0 < length <= _MAX_BODY:
                raise ResearchError("INVALID_INPUT", "JSON request body must be at most 1 MiB")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ResearchError("INVALID_INPUT", "Content-Type must be application/json")
            payload = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite JSON is not accepted")))
            if not isinstance(payload, dict) or set(payload) != {"tool", "arguments"}:
                raise ResearchError("INVALID_INPUT", "Request must contain tool and arguments only")
            result = call_tool(self.server.bridge, payload["tool"], payload["arguments"])
            self._send(200, result)
        except ResearchError as exc:
            # Scope rejection uses the same operational envelope as Bridge. Input
            # contract failures are HTTP 400; no transition has run at this point.
            self._send(200 if exc.code == "PERMISSION_DENIED" else 400, _error(exc.code, str(exc), exc.details))
        except (OSError, ValueError, TypeError, UnicodeError, sqlite3.Error) as exc:
            self._send(400, _error("INVALID_INPUT", str(exc)))

    def do_OPTIONS(self):
        self._send(403, _error("PERMISSION_DENIED", "Cross-origin access is not supported"))


def create_server(root, host="127.0.0.1", port=0):
    """Create a loopback server without starting threads or modifying research state."""
    if host != "127.0.0.1":
        raise ValueError("The research web channel only listens on 127.0.0.1")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer between 0 and 65535")
    server = _Server((host, port), _Handler)
    server.bridge = _WebBridge(root)
    server.session_token = secrets.token_urlsafe(32)
    return server


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="research-state-web", description="Local research dashboard and browser WebMCP channel; model calls remain external")
    parser.add_argument("--root", required=True, help="Dedicated root containing relative research workspaces")
    parser.add_argument("--port", type=int, default=8765, help="Loopback HTTP port (default 8765; 0 chooses an available port)")
    parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser")
    args = parser.parse_args(argv)
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    try:
        server = create_server(args.root, port=args.port)
    except (OSError, ValueError) as exc:
        print("Cannot start research web dashboard: " + str(exc), file=sys.stderr)
        return 2
    url = "http://%s:%s/" % server.server_address
    print(json.dumps({"ok": True, "data": {"url": url, "root": str(server.bridge.root), "version": __version__}}, ensure_ascii=False), flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
