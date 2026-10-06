"""Portable state/evidence snapshots; never start a task during restore."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from .core import ResearchError, Store, canonical, sha256_file


def export(store, output):
    output = output.resolve()
    if output.exists():
        raise ResearchError('CONFLICT', 'Export destination already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        backup = Path(temporary)/'state.sqlite3'
        with closing(sqlite3.connect(store.db_path)) as source, closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
        files = {'.research/'+store.db_path.name: backup}
        # Only immutable evidence and fixed verifier files are needed for replay.
        # Mutable worker state and local authority keys are deliberately excluded.
        references = {}
        with closing(sqlite3.connect(backup)) as snapshot:
            for path, expected in snapshot.execute('SELECT path,sha256 FROM evidence WHERE path IS NOT NULL'):
                references[path] = expected
            for (record,) in snapshot.execute('SELECT record FROM validators'):
                references.update(json.loads(record)['hashes'])
        for name, expected in references.items():
            path = (store.root/name).resolve()
            if not path.is_relative_to(store.metadata_dir.resolve()) or sha256_file(path) != expected:
                raise ResearchError('EVIDENCE_INVALID', 'Cannot export missing or changed evidence: '+name)
            files[name] = path
        manifest = {'format': 'research-state-export-v1', 'files': {
            name: {'sha256': sha256_file(path), 'bytes': path.stat().st_size}
            for name, path in sorted(files.items())},
            'pending_execution_policy': 'running/unknown remain unresolved; restore never launches a worker',
            'authority_policy': 'new local capabilities on restore; no authority keys exported'}
        temporary_output = output.with_suffix(output.suffix+'.tmp')
        with zipfile.ZipFile(temporary_output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in files.items():
                archive.write(path, name)
            archive.writestr('manifest.json', canonical(manifest))
        with zipfile.ZipFile(temporary_output) as archive:
            for name, metadata in manifest['files'].items():
                with archive.open(name) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != metadata['sha256']:
                        temporary_output.unlink(missing_ok=True)
                        raise ResearchError('EVIDENCE_INVALID', 'Evidence changed while exporting: '+name)
        temporary_output.replace(output)
    return {'path': str(output), 'sha256': sha256_file(output), 'files': len(files)}


def restore(root, source):
    root = root.resolve()
    if root.exists() and any(root.iterdir()):
        raise ResearchError('CONFLICT', 'Restore needs a new empty workspace')
    try:
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate archive entries')
            manifest = json.loads(archive.read('manifest.json'))
            if manifest['format'] != 'research-state-export-v1':
                raise ValueError('Unsupported export format')
            expected_names = set(manifest['files']) | {'manifest.json'}
            if set(names) != expected_names:
                raise ValueError('Unexpected or missing archive entries')
            verified = {}
            for name, metadata in manifest['files'].items():
                destination = (root/name).resolve()
                if not name.startswith('.research/') or not destination.is_relative_to(root/'.research') or '\\' in name or '..' in Path(name).parts:
                    raise ValueError('Unsafe archive path')
                if name.endswith('/owner.key') or name.endswith('/internal.key'):
                    raise ValueError('Authority keys are not exportable')
                content = archive.read(name)
                if len(content) != metadata['bytes'] or hashlib.sha256(content).hexdigest() != metadata['sha256']:
                    raise ValueError('Export evidence hash mismatch: '+name)
                verified[name] = content
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise ResearchError('EVIDENCE_INVALID', str(exc)) from exc
    # Verify the database before writing a partial destination.
    db_name = '.research/state.sqlite3' if '.research/state.sqlite3' in verified else None
    if db_name is None:
        raise ResearchError('EVIDENCE_INVALID', 'State database missing')
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary)/'check.sqlite3'
        database.write_bytes(verified[db_name])
        with closing(sqlite3.connect(database)) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ResearchError('EVIDENCE_INVALID', 'Database integrity check failed')
            try:
                if connection.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() not in (('1',), ('2',)):
                    raise ValueError('Unsupported database schema')
                references = dict(connection.execute('SELECT path,sha256 FROM evidence WHERE path IS NOT NULL'))
                for (record,) in connection.execute('SELECT record FROM validators'):
                    references.update(json.loads(record)['hashes'])
                for name, expected in references.items():
                    if name not in manifest['files'] or manifest['files'][name]['sha256'] != expected:
                        raise ValueError('Database evidence reference does not match manifest: '+name)
            except (sqlite3.Error, ValueError, KeyError) as exc:
                raise ResearchError('EVIDENCE_INVALID', str(exc)) from exc
    initialized = Store.init(root)
    for name, content in verified.items():
        destination = root/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    # v1 archives are extended without changing experiment records or launching.
    Store(root)
    return {'workspace': str(root), 'files': len(verified), 'owner_key_path': initialized['owner_key_path'],
            'resume': 'Inspect status; archived running/unknown executions are never automatically rerun'}
