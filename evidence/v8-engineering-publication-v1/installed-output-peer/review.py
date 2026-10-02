"""Read-only v8 installed-output peer; never imports or executes release/package code.

Role disclosure: this reviewer authored the narrow v4 external release-helper
reference-count correction. Root independently reviewed that helper. This audit
recomputes the installed output and recorded validation, not an independent
review of this author's helper implementation or a repeat of the tests.
"""
from __future__ import annotations
import ast
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RELEASE = PROJECT / 'versions/v8-development'
PROOF = RELEASE / 'validation/release-local-v1'
SOURCE = PROJECT / 'work/c8-implementation-v1/source-manifest.json'
GO = PROJECT / 'work/c8-root-release-go-v4/parent-go.json'
PINS = {
    'source_manifest': '6fce28fb5ed196717011906b9071091244f72bd7874728f2114cb399d2468d69',
    'root_go': '4819ded65a7b74223b1d2490d849730179e9e52ff9cf6b5fa9e99517644809f4',
    'release_copy': '4a78bb5d5d330e039cabc44d85272957254e1947c515b0aaa0548d91dd5816bd',
    'validation_result': '2f4b8fd8a3efa890892b5faa387c9c4be353dff879f9f1b6541bedf422529877',
    'release_helper': '2985da34018d98d4759c74b3a64798700ee055dae0f588bfe263d71bfe052720',
    'release_guard': '54460042ef7d29d02f8c021a5bed3123193a5ce3255a9897709b2df6291f2d08',
    'method': '21bc0d8ddb1cd3e2bb8b77c958fe7540d972318f3b6bd691406db2bb8b0f2298',
    'whole_prerequisite': '69c1d5d9793aebed25e7dd52623008b12b5ec8242d081bd2c82cfa5d39701484',
    'ten_family_prerequisite': '6a2e547bec77f7d7d71b434a40284c14d00b4d0f4a25716af766a232d93b2377',
    'semantic_module': 'bcfb3dc95facb0eeaec52ee5587c512a654a0aebc2316ff9f4ef98c53b06e529',
    'upstream_manifest': '2b02fc8f6d2fef3f46758cb2e6855686371c94ac055298badf7d2f8970c3587f',
    'semantic_facts': '54217c18c38a544c9ee1094eb772170914d3f0277f9ba88ffd4192d236344907',
    'literature_corpus': '64d0f27c0faae3d18fb4a57e24de80c2612ee0785936ddfa79f754aa91c6e5c9',
    'added_example': '6deca8e6402e6048d67f35ee55635414b869e986abd9155de219191b4e72cd55',
    'root_validation_execution_declared': '34f7b25310f40064e50847319e7a2f195c45f1ed1a91904678f2dfa2d0511925',
}
PHASES = ('venv-create', 'offline-editable-install', 'clean-runtime',
          'cli-help', 'frozen-closure', 'unit-checks')
REFERENCE_DOCUMENTS = {'references/README.md', 'references/AgentLaboratory.LICENSE'}
VERSION = '0.4.1.dev0'
BUNDLED = Path(r'C:\Users\Potato\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
ALLOWED = {SOURCE.resolve(), GO.resolve(), (RELEASE/'release-copy.json').resolve(),
           (PROOF/'result.json').resolve(), (PROOF/'before.json').resolve(),
           (PROOF/'after.json').resolve(), (PROOF/'unit-guard.json').resolve(),
           (PROOF/'audit_guard/sitecustomize.py').resolve(), Path(__file__).resolve()}
for _phase in PHASES:
    for _extension in ('json', 'stdout.log', 'stderr.log'):
        ALLOWED.add((PROOF/f'{_phase}.{_extension}').resolve())
COUNTS = {'outside_allowed_file_reads': 0, 'process_attempts': 0,
          'network_attempts': 0, 'directory_discovery_attempts': 0}
READS: dict[str, dict] = {}

def require(value, message):
    if not value:
        raise ValueError(message)

def audit(event, args):
    if event == 'open' and not isinstance(args[0], int):
        path = Path(args[0]).resolve()
        mode = args[1] or ''
        flags = args[2]
        writing = any(k in mode for k in 'wax+') or (isinstance(flags, int) and flags & 3)
        allowed = path.is_relative_to(HERE.resolve()) if writing else path in ALLOWED
        if not allowed:
            COUNTS['outside_allowed_file_reads'] += 1
            raise PermissionError('Read/write outside explicit static output audit scope')
    if event.startswith(('subprocess.', 'os.system', 'os.spawn', 'os.exec')):
        COUNTS['process_attempts'] += 1
        raise PermissionError('Process execution forbidden in output peer')
    if event.startswith('socket.'):
        COUNTS['network_attempts'] += 1
        raise PermissionError('Network forbidden in output peer')
    if event in ('os.listdir', 'os.scandir'):
        COUNTS['directory_discovery_attempts'] += 1
        raise PermissionError('Use fixed inventories, never directory discovery')

sys.addaudithook(audit)

def relative(value):
    require(isinstance(value, str), 'Non-string inventory path')
    part = PurePosixPath(value)
    require(part.parts and not part.is_absolute() and part.as_posix() == value and
            '..' not in part.parts and '\\' not in value and ':' not in value and
            all(not x.endswith(('.', ' ')) for x in part.parts), 'Unsafe source path')
    require(not any(x.lower().startswith(('owner-', 'private')) for x in part.parts)
            and part.parts[0] not in ('runs', '.venv', 'work'), 'Actual/private/runtime inventory forbidden')
    return Path(*part.parts)

def checked(root, name):
    path = root/relative(name)
    node = root
    for component in (None, *relative(name).parts):
        if component is not None:
            node /= component
        require(not node.is_symlink() and not (hasattr(node, 'is_junction') and node.is_junction()),
                'Symlink/junction rejected')
    require(path.resolve().is_relative_to(root.resolve()), 'Source escapes pinned release root')
    return path

def raw(path, digest=None):
    path = Path(path)
    data = path.read_bytes()
    measured = hashlib.sha256(data).hexdigest()
    if digest is not None:
        require(measured == digest, 'External SHA mismatch: '+path.name)
    READS[str(path.relative_to(PROJECT)) if path.is_relative_to(PROJECT) else str(path)] = {
        'sha256': measured, 'bytes': len(data)}
    return data

def load(path, digest=None):
    return json.loads(raw(path, digest).decode('utf-8'))

def constants(data):
    values = {}
    for node in ast.parse(data.decode('utf-8')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
    return values

def main():
    source = load(SOURCE, PINS['source_manifest'])
    require(source['file_count'] == 110 and len(source['files']) == 110 and
            source['method_registration_sha256'] == PINS['method'], 'Source110 original binding differs')
    basis = {}
    sizes = {}
    for row in source['files']:
        relative(row['relative'])
        require(row['relative'] not in basis and re.fullmatch('[a-f0-9]{64}', row['sha256']),
                'Duplicate/malformed original source inventory')
        basis[row['relative']] = row['sha256']
        sizes[row['relative']] = row['bytes']
    go = load(GO, PINS['root_go'])
    require(go['kind'] == 'version8_release_execution_contract' and
            go['source_manifest_sha256'] == PINS['source_manifest'] and
            go['method_registration_sha256'] == PINS['method'] and
            go['helper_source_sha256'] == PINS['release_helper'] and
            go['guard_source_sha256'] == PINS['release_guard'] and
            go['whole_review']['sha256'] == PINS['whole_prerequisite'] and
            go['independent_review']['sha256'] == PINS['ten_family_prerequisite'] and
            go['template_is_not_authorization'] is False and go['no_actual_research'] is True and
            go['actual_study_launch_authorized'] is False and Path(go['target']).resolve() == RELEASE.resolve(),
            'Externally authorized engineering GO binding differs')
    expected = dict(basis)
    require(len(go['document_overrides']) == 2, 'Exactly two documented overrides expected')
    for row in go['document_overrides']:
        require(row['relative'] in ('README.md', 'docs/c8_callback_context_repair.ko.md') and
                row['basis_sha256'] == basis[row['relative']] and
                row['qualification'] == 'publication_scope_derived_documentation', 'Document scope differs')
        expected[row['relative']] = row['sha256']
    additions = go['added_metadata_files']
    require(len(additions) == 1 and additions[0]['relative'] == 'examples/sampled-pilot-base-v8.json'
            and additions[0]['sha256'] == PINS['added_example'] and
            additions[0]['qualification'] == 'prospective_metadata_only_no_study', 'Metadata addition differs')
    expected[additions[0]['relative']] = additions[0]['sha256']
    require(len(expected) == 111, 'Runtime111 expected')
    for name in expected:
        ALLOWED.add(checked(RELEASE, name).resolve())
    copied = load(RELEASE/'release-copy.json', PINS['release_copy'])
    require(copied['files'] == expected and copied['basis_files'] == basis and
            copied['document_overrides'] == go['document_overrides'] and
            copied['added_metadata_files'] == additions and copied['source_file_count'] == 111 and
            copied['basis_source_file_count'] == 110 and copied['go_contract_sha256'] == PINS['root_go'] and
            copied['source_manifest_sha256'] == PINS['source_manifest'] and copied['version'] == VERSION and
            copied['actual_model_calls'] == 0 and copied['research_trials'] == 0 and
            copied['study_registration'] is False, 'Externally fixed release copy is inconsistent')
    before = load(PROOF/'before.json')
    after = load(PROOF/'after.json')
    require(before['source'] == after['source'] == expected, 'Before/after runtime111 map differs')
    require(before['protected_sources'] == after['protected_sources'] and
            len(before['protected_sources']) == 417, 'Recorded protected417 maps differ')
    measured = {}
    data = {}
    for name, digest in expected.items():
        data[name] = raw(checked(RELEASE, name), digest)
        measured[name] = hashlib.sha256(data[name]).hexdigest()
        if name not in {r['relative'] for r in go['document_overrides']} and name in basis:
            require(len(data[name]) == sizes[name], 'Source byte size differs')
    package = {x for x in expected if x.startswith('evidence_research/') and x.endswith('.py')}
    fullrefs = {x for x in expected if x.startswith('references/')}
    closure = fullrefs-REFERENCE_DOCUMENTS
    require(len(package) == 20 and len(fullrefs) == 40 and REFERENCE_DOCUMENTS.issubset(fullrefs)
            and len(closure) == 38, 'Package20/reference40/closure38/documents2 differ')
    pyproject = tomllib.loads(data['pyproject.toml'].decode('utf-8'))
    require(pyproject['project']['version'] == VERSION and pyproject['project']['dependencies'] == [] and
            constants(data['evidence_research/__init__.py'])['__version__'] == VERSION,
            'Package metadata/version/dependencies differ')
    require(expected['evidence_research/report_semantics.py'] == PINS['semantic_module'] and
            expected['references/manifest.json'] == PINS['upstream_manifest'] and
            expected['references/source_facts_c7.json'] == PINS['semantic_facts'] and
            expected['references/task_literature_v2.json'] == PINS['literature_corpus'],
            'External semantic/literature/upstream pins differ')
    base = constants(data['evidence_research/baseline.py'])
    upstream = json.loads(data['references/manifest.json'])
    originals = [x for x in upstream['files'] if 'upstream_path' in x]
    require(len(originals) == 35 and upstream['upstream_commit'] == base['UPSTREAM_COMMIT'],
            'Upstream35 original commit differs')
    for row in originals:
        blob = data[row['path']]
        require(expected[row['path']] == row['sha256'] and len(blob) == row['bytes'] and
                hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest() == row['git_blob_sha1'],
                'Authenticated source35 SHA/size/Git blob differs')
    for module, digest in base['UPSTREAM_MODULE_SHA256'].items():
        name = f"references/upstream/AgentLaboratory-{base['UPSTREAM_COMMIT']}/{module}.py"
        require(expected[name] == digest, 'Executable original module pin differs')
    value = load(PROOF/'result.json', PINS['validation_result'])
    require(value['valid'] is True and value['checks'] == 276 and
            value['source_file_count'] == 111 and value['basis_source_file_count'] == 110 and
            value['source_unchanged'] is True and value['protected_sources_unchanged'] is True and
            value['protected_source_files'] == 417 and value['copy_receipt_sha256'] == PINS['release_copy'] and
            value['go_contract_sha256'] == PINS['root_go'], 'New validation receipt differs')
    venv = RELEASE/'.venv'
    python = venv/'Scripts/python.exe'
    clean_code = 'import sys,site,json,importlib.metadata as m,evidence_research as e;print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,"user_site":site.ENABLE_USER_SITE,"package_path":e.__file__,"version":m.version("evidence-research"),"module_version":e.__version__}))'
    closure_code = 'import json;from evidence_research.baseline import frozen_upstream_sources;from evidence_research.report_semantics import frozen_semantic_reference_hashes;print(json.dumps({"upstream":frozen_upstream_sources(),"semantic":frozen_semantic_reference_hashes()}))'
    prefix = [str(python), '-X', 'utf8', '-B']
    commands = {
        'venv-create': [str(BUNDLED), '-X', 'utf8', '-B', '-m', 'venv', str(venv)],
        'offline-editable-install': prefix+['-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps', '--no-build-isolation', '--editable', '.'],
        'clean-runtime': prefix+['-c', clean_code],
        'cli-help': prefix+['-m', 'evidence_research', '--help'],
        'frozen-closure': prefix+['-c', closure_code],
        'unit-checks': prefix+['-m', 'unittest', 'discover', '-s', 'tests', '-v'],
    }
    require([p['phase'] for p in value['phases']] == list(PHASES), 'Recorded six-phase order differs')
    phase_outputs = {}
    for item in value['phases']:
        name = item['phase']
        recorded = load(PROOF/f'{name}.json')
        require(recorded == item and item['exit_code'] == 0 and item['command'] == commands[name] and
                isinstance(item['seconds'], (float, int)) and not isinstance(item['seconds'], bool) and
                math.isfinite(item['seconds']) and item['seconds'] >= 0, 'Phase command/exit/receipt differs: '+name)
        phase_outputs[name] = (raw(PROOF/f'{name}.stdout.log', item['stdout_sha256']),
                               raw(PROOF/f'{name}.stderr.log', item['stderr_sha256']))
    runtime = json.loads(phase_outputs['clean-runtime'][0])
    require(runtime == value['environment'] and Path(runtime['prefix']).resolve() == venv.resolve() and
            Path(runtime['base_prefix']).resolve() == BUNDLED.parent.resolve() and
            runtime['prefix'] != runtime['base_prefix'] and runtime['user_site'] is False and
            Path(runtime['package_path']).resolve() == (RELEASE/'evidence_research/__init__.py').resolve() and
            runtime['version'] == runtime['module_version'] == VERSION, 'Own clean runtime output differs')
    require(b'Successfully installed evidence-research-0.4.1.dev0' in phase_outputs['offline-editable-install'][0]
            and b'usage:' in phase_outputs['cli-help'][0], 'Offline editable install/CLI help output missing')
    runtime_refs = json.loads(phase_outputs['frozen-closure'][0])
    require(set(runtime_refs) == {'upstream', 'semantic'}, 'Frozen closure output groups differ')
    observed = {}
    for group in runtime_refs.values():
        for path, digest in group.items():
            require(Path(path).is_absolute() and Path(path).resolve().is_relative_to(RELEASE.resolve()),
                    'Observed closure path escapes release')
            name = Path(path).relative_to(RELEASE).as_posix()
            require(name not in observed, 'Duplicate runtime closure entry')
            observed[name] = digest
    require(observed == {name:expected[name] for name in closure}, 'Runtime closure38 differs')
    unittest_log = phase_outputs['unit-checks'][1].decode('utf-8')
    require(re.search(r'Ran 276 tests in [0-9.]+s\s+\s*OK\s*\Z', unittest_log) is not None,
            'Original raw276 unittest completion absent')
    require(len(re.findall(r'^test_[^\n]+ \.\.\. ok\r?$', unittest_log, flags=re.M)) == 276,
            'Original raw test success line inventory differs')
    guard = load(PROOF/'unit-guard.json')
    require(guard == value['guard'] and set(guard['counts']) == {
            'other_project_or_version_access_attempts', 'live_study_access_attempts',
            'nonfixture_process_attempts', 'network_events', 'allowed_cpu_fixture_subprocesses'} and
            all(x == 0 for k,x in guard['counts'].items() if k != 'allowed_cpu_fixture_subprocesses') and
            guard['counts']['allowed_cpu_fixture_subprocesses'] == 1, 'Recorded validation guard differs')
    raw(PROOF/'audit_guard/sitecustomize.py', PINS['release_guard'])
    require('not an OS sandbox' in guard['scope'] and 'not covered' in guard['scope'] and
            'No OS-wide' in value['guard_limit'], 'Guard limitation was omitted')
    require(all(value[key] == 0 for key in ('actual_model_calls', 'actual_research_trials', 'external_dependency_downloads'))
            and all(value[key] is False for key in ('study_registration', 'inherited_credentials_copied',
                'doctor_or_authentication_check', 'framework_improvement_proven', 'goal_complete')),
            'Engineering scope flags differ')
    # Rehash precisely the same allowed source files; no protected-body reads.
    again = {name:hashlib.sha256(raw(checked(RELEASE, name))).hexdigest() for name in expected}
    require(again == measured, 'New runtime111 changed during output audit')
    return {
        'status': 'pass', 'kind': 'version8_installed_output_static_peer', 'external_pins': PINS,
        'role_disclosure': 'Author of the narrow v4 external release-helper reference-count correction; root independently reviewed its implementation. This output/log check is not an independent helper implementation review.',
        'basis_sources': 110, 'runtime_sources': 111, 'package_modules': 20,
        'reference_files_total': 40, 'reference_closure_files': 38, 'authenticated_reference_documents': 2,
        'upstream_authenticated_files': 35, 'source_bytes_verified': True, 'source_stable_during_peer': True,
        'document_overrides': 2, 'prospective_metadata_additions': 1,
        'own_venv': True, 'version': VERSION, 'user_site': False,
        'recorded_phases_verified': 6, 'recorded_unittest_success_lines': 276,
        'recorded_protected_source_maps_equal': True, 'protected_map_entries': 417,
        'protected_source_bodies_reopened': 0,
        'validation_guard': guard, 'peer_guard': {'counts':dict(COUNTS),
            'scope':'Explicit fixed read inventory; no package/helper imports, directory discovery, process or network. Python hook is not an OS-wide guard.'},
        'new_test_or_cli_runs': 0, 'new_environments': 0, 'new_actual_providers_or_cpu_research': 0,
        'private_owner_reads': 0, 'git_or_publication_actions': 0, 'findings': [],
        'limitations': [
            'Tests were not repeated; original new-environment log/receipts were recomputed and checked.',
            'Old protected417 unchanged is a before/after metadata consistency check; their original bodies were not opened by this peer.',
            'Parent validation hook does not cover the one allowed tiny CPU child and is not an OS-wide or all-sibling read proof.',
            'No authentication or provider access was attempted or proved; zero-action flags are recorded root execution scope corroborated by the fixed commands/guard.',
            'Successful engineering installation and tests do not prove research improvement or complete the Goal.',
        ],
    }

if __name__ == '__main__':
    try:
        result = main()
    except BaseException as error:
        result = {'status':'failed', 'kind':'version8_installed_output_static_peer',
            'failure':{'type':type(error).__name__, 'message':str(error)},
            'external_pins':PINS, 'peer_guard':{'counts':dict(COUNTS)},
            'new_test_or_cli_runs':0, 'new_actual_providers_or_cpu_research':0,
            'role_disclosure':'Author of corrected external release helper; installed-output static reviewer.'}
    result['read_inventory'] = dict(READS)
    with (HERE/'result.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'read_inventory'}, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'pass' else 1)
