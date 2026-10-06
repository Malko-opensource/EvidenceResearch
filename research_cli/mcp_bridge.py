"""Thin JSON-object transport for the existing CLI dispatch; no SDK dependency."""
import json
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
import sqlite3

from .cli import dispatch
from .core import ResearchError, Store, canonical


OPERATIONS = {
    'help': {'topic'}, 'init': set(), 'goal': {'title', 'description', 'brief', 'request_key', 'expect'},
    'goal_show': {'goal', 'limit', 'offset'},
    'goal_amend': {'goal', 'brief', 'title', 'description', 'reason', 'change_kind', 'request_key', 'expect'},
    'goal_close': {'goal', 'state', 'reason', 'results', 'incomplete', 'request_key', 'expect'},
    'goal_resume': {'goal', 'reason', 'request_key', 'expect'},
    'resource': {'goal', 'observation', 'request_key', 'expect'},
    'resource_show': {'goal', 'limit', 'offset'},
    'hypothesis': {'goal', 'statement', 'expect'},
    'register': {'goal', 'input', 'request_key', 'expect'},
    'status': {'goal', 'limit', 'offset'},
    'memory': {'query', 'outcome', 'verification', 'limit', 'offset'},
    'show': {'registration'}, 'run': {'registration', 'request_key', 'expect', 'full'},
    'recover': {'registration', 'full'}, 'verify': {'registration', 'full'},
    'decide': {'registration', 'decision', 'reason', 'expect'},
    'evidence': {'registration', 'kind', 'claim', 'path', 'expect'},
    'export': {'output'}, 'restore': {'input'},
    'laya_prepare': {'input'}, 'laya_resolve': {'input', 'response', 'expected_sha256'}}

DEFAULTS = {'topic': None, 'description': '', 'expect': None, 'goal': None,
            'limit': 20, 'offset': 0, 'query': '', 'outcome': None, 'verification': None,
            'full': False, 'path': None, 'output': None, 'input': None,
            'brief': {}, 'request_key': None, 'title': None, 'results': [], 'incomplete': []}


class Bridge:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def workspace(self, name):
        if not isinstance(name, str) or not name.strip():
            raise ResearchError('INVALID_INPUT', 'workspace must be a nonempty relative directory')
        relative, windows = Path(name), PureWindowsPath(name)
        if relative.is_absolute() or windows.is_absolute() or windows.drive or ':' in name or '..' in relative.parts or '..' in windows.parts:
            raise ResearchError('INVALID_INPUT', 'workspace must stay beneath the configured research root')
        path = (self.root / relative).resolve()
        if path == self.root:
            raise ResearchError('INVALID_INPUT', 'Choose a workspace directory beneath the research root')
        if not path.is_relative_to(self.root):
            raise ResearchError('PERMISSION_DENIED', 'Workspace link leaves the configured research root')
        return path

    def _file(self, value, workspace):
        if not isinstance(value, str) or not value:
            raise ResearchError('INVALID_INPUT', 'Expected a file path beneath the configured research root')
        path = Path(value)
        if not path.is_absolute():
            path = workspace / path
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ResearchError('PERMISSION_DENIED', 'File path leaves the configured research root')
        return str(path)

    @staticmethod
    def _experiment_cwd(cwd, workspace):
        if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute():
            raise ResearchError('INVALID_INPUT', 'Experiment cwd must be absolute beneath this workspace')
        if not Path(cwd).resolve().is_relative_to(workspace):
            raise ResearchError('PERMISSION_DENIED', 'Experiment cwd leaves this workspace')

    def call(self, operation, workspace='default', **parameters):
        try:
            if operation not in OPERATIONS or set(parameters) - OPERATIONS[operation]:
                raise ResearchError('INVALID_INPUT', 'Unknown MCP operation or parameters')
            path = self.workspace(workspace)
            parameters = json.loads(canonical(parameters))
            values = DEFAULTS | parameters
            if operation == 'goal_amend' and 'description' not in parameters:
                values['description'] = None
            if operation == 'register':
                spec = values.get('input')
                if not isinstance(spec, dict):
                    raise ResearchError('INVALID_INPUT', 'Registration input must be a JSON object')
                self._experiment_cwd(spec.get('cwd'), path)
            if operation == 'run':
                record = Store(path).show(values['registration'])
                # CLI-created or restored registrations have not passed the MCP
                # registration scope check. Check before claiming a new run;
                # existing runs can only be reused, never relaunched.
                if record['run'] is None:
                    self._experiment_cwd(record['registration']['spec'].get('cwd'), path)
            if operation == 'evidence' and values['path'] is not None:
                values['path'] = self._file(values['path'], path)
            if operation == 'export':
                values['output'] = self._file(values.get('output'), path)
            if operation == 'restore':
                values['input'] = self._file(values.get('input'), path)
            command = 'laya' if operation.startswith('laya_') else operation
            if command == 'laya':
                if not isinstance(values.get('input'), dict):
                    raise ResearchError('INVALID_INPUT', 'Laya input must be a JSON object')
                if operation == 'laya_resolve' and not isinstance(values.get('response'), dict):
                    raise ResearchError('INVALID_INPUT', 'Laya response must be a JSON object')
                values['laya_action'] = operation.removeprefix('laya_')
            result = dispatch(SimpleNamespace(workspace=str(path), command=command, **values))
            if operation in ('init', 'restore'):
                result = {name: value for name, value in result.items()
                          if name not in ('owner_key_path', 'internal_key_path')}
            return {'ok': True, 'data': result}
        except ResearchError as exc:
            return {'ok': False, 'error': {'code': exc.code, 'message': str(exc), 'details': exc.details}}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as exc:
            return {'ok': False, 'error': {'code': 'INVALID_INPUT', 'message': str(exc), 'details': {}}}
