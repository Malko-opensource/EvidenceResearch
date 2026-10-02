"""Finish only the raw276 parser and previously unvisited guard/drift checks.

The initial review and its failure are immutable. No successful installation,
test, CLI, or earlier completed output-audit phase is repeated here.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
RELEASE = PROJECT/'versions/v8-development'
PROOF = RELEASE/'validation/release-local-v1'
PINS = {
    'initial_review_helper': 'b8c4f99e267ae6e848ffd415d04140181a29ef748ed812612249d07f683a4cf4',
    'initial_failed_result': '3bcb05172cab56e471725e7d5bd3df7cfe32e41756b5aa79457c6d80d6dbefed',
    'release_copy': '4a78bb5d5d330e039cabc44d85272957254e1947c515b0aaa0548d91dd5816bd',
    'validation_result': '2f4b8fd8a3efa890892b5faa387c9c4be353dff879f9f1b6541bedf422529877',
    'source_manifest': '6fce28fb5ed196717011906b9071091244f72bd7874728f2114cb399d2468d69',
    'root_go': '4819ded65a7b74223b1d2490d849730179e9e52ff9cf6b5fa9e99517644809f4',
    'release_guard': '54460042ef7d29d02f8c021a5bed3123193a5ce3255a9897709b2df6291f2d08',
}
ALLOWED = {HERE/'result.json', HERE/'review.py', RELEASE/'release-copy.json',
           PROOF/'result.json', PROOF/'unit-checks.stderr.log', PROOF/'unit-guard.json',
           PROOF/'audit_guard/sitecustomize.py'}
ALLOWED = {p.resolve() for p in ALLOWED}
COUNTS = {'outside_allowed_file_reads': 0, 'process_attempts': 0,
          'network_attempts': 0, 'directory_discovery_attempts': 0}
READS = {}

def require(value, message):
    if not value:
        raise ValueError(message)

def audit(event, args):
    if event == 'open' and not isinstance(args[0], int):
        path = Path(args[0]).resolve()
        mode, flags = args[1] or '', args[2]
        writing = any(k in mode for k in 'wax+') or (isinstance(flags, int) and flags & 3)
        if not (path.is_relative_to(HERE.resolve()) if writing else path in ALLOWED):
            COUNTS['outside_allowed_file_reads'] += 1
            raise PermissionError('Explicit finish-only read/write inventory required')
    if event.startswith(('subprocess.', 'os.system', 'os.spawn', 'os.exec')):
        COUNTS['process_attempts'] += 1
        raise PermissionError('No processes')
    if event.startswith('socket.'):
        COUNTS['network_attempts'] += 1
        raise PermissionError('No network')
    if event in ('os.listdir', 'os.scandir'):
        COUNTS['directory_discovery_attempts'] += 1
        raise PermissionError('No directory discovery')

sys.addaudithook(audit)

def raw(path, digest=None):
    path = Path(path)
    value = path.read_bytes()
    measured = hashlib.sha256(value).hexdigest()
    require(digest is None or measured == digest, 'Pinned input differs: '+path.name)
    READS[path.relative_to(PROJECT).as_posix()] = {'sha256':measured, 'bytes':len(value)}
    return value

def load(path, digest=None):
    return json.loads(raw(path, digest))

def source_path(name):
    part = PurePosixPath(name)
    require(isinstance(name, str) and part.parts and part.as_posix() == name and
            not part.is_absolute() and '..' not in part.parts and '\\' not in name and ':' not in name and
            part.parts[0] not in ('runs', '.venv', 'work') and
            not any(x.lower().startswith(('owner-', 'private')) for x in part.parts), 'Unsafe source111 member')
    path = RELEASE/Path(*part.parts)
    current = RELEASE
    for element in (None, *part.parts):
        if element is not None:
            current /= element
        require(not current.is_symlink() and not (hasattr(current, 'is_junction') and current.is_junction()),
                'Source symlink/junction rejected')
    require(path.resolve().is_relative_to(RELEASE.resolve()), 'Source111 outside own root')
    return path

def main():
    original = load(HERE/'result.json', PINS['initial_failed_result'])
    raw(HERE/'review.py', PINS['initial_review_helper'])
    require(original['status'] == 'failed' and original['failure'] == {
        'type':'ValueError', 'message':'Original raw test success line inventory differs'} and
        not any(original['peer_guard']['counts'].values()), 'Wrong initial failure site or guard')
    require(original['external_pins']['root_go'] == PINS['root_go'] and
            original['external_pins']['source_manifest'] == PINS['source_manifest'], 'Initial external basis differs')
    prior_reads = original['read_inventory']
    copied = load(RELEASE/'release-copy.json', PINS['release_copy'])
    validation = load(PROOF/'result.json', PINS['validation_result'])
    require(copied['source_file_count'] == 111 and len(copied['files']) == 111 and
            copied['source_manifest_sha256'] == PINS['source_manifest'] and
            copied['go_contract_sha256'] == PINS['root_go'] and validation['valid'] is True and
            validation['checks'] == 276, 'Completed installed-output audit continuation binding differs')
    for name, digest in copied['files'].items():
        path = source_path(name)
        key = str(path.relative_to(PROJECT))
        require(prior_reads[key]['sha256'] == digest, 'Original pre-parser source audit absent')
        ALLOWED.add(path.resolve())
    # The pinned initial reviewer completed six command/receipt/log comparisons,
    # own-runtime/closure checks and protected before/after map comparison before
    # raising at the fixed single-line-success inventory assertion. No re-exec.
    require(len(validation['phases']) == 6 and
            all(p['exit_code'] == 0 for p in validation['phases']), 'Recorded prior six phases not complete')
    unit = validation['phases'][-1]
    require(unit['phase'] == 'unit-checks', 'Raw unit phase missing')
    text = raw(PROOF/'unit-checks.stderr.log', unit['stderr_sha256']).decode('utf-8')
    require(re.search(r'Ran 276 tests in [0-9.]+s\s+\s*OK\s*\Z', text), 'Raw276 completion absent')
    blocks = re.findall(r'^test_[^\n]*(?:\n(?!test_)[^\n]*)*', text, flags=re.M)
    require(len(blocks) == 276, 'Raw276 original test-start inventory differs')
    multiline = []
    for block in blocks:
        statuses = re.findall(r'(?:\.\.\. |^)ok\r?$', block, flags=re.M)
        require(len(statuses) == 1, 'Test does not have exactly one raw success completion')
        if '\n' in block and not re.search(r'^test_[^\n]* \.\.\. ok\r?$', block, flags=re.M):
            multiline.append(block.splitlines()[0].split(' ')[0])
    require(multiline == ['test_pinned_original_bytes_can_be_parsed_without_running_any_phase'] and
            "SyntaxWarning: invalid escape sequence '\\%'" in text,
            'Interleaved original syntax warning differs from recorded parser limitation')
    guard = load(PROOF/'unit-guard.json')
    require(guard == validation['guard'] and set(guard['counts']) == {
        'other_project_or_version_access_attempts', 'live_study_access_attempts',
        'nonfixture_process_attempts', 'network_events', 'allowed_cpu_fixture_subprocesses'} and
        all(v == 0 for k,v in guard['counts'].items() if k != 'allowed_cpu_fixture_subprocesses') and
        guard['counts']['allowed_cpu_fixture_subprocesses'] == 1, 'Recorded guard differs')
    raw(PROOF/'audit_guard/sitecustomize.py', PINS['release_guard'])
    require('not an OS sandbox' in guard['scope'] and 'not covered' in guard['scope'] and
            'No OS-wide' in validation['guard_limit'], 'Guard scope caveat missing')
    require(all(validation[k] == 0 for k in ('actual_model_calls', 'actual_research_trials', 'external_dependency_downloads'))
            and all(validation[k] is False for k in ('study_registration', 'inherited_credentials_copied',
                'doctor_or_authentication_check', 'framework_improvement_proven', 'goal_complete')),
            'Engineering-only receipt scope differs')
    after = {name:hashlib.sha256(raw(source_path(name))).hexdigest() for name in copied['files']}
    require(after == copied['files'], 'Source111 drift after original static audit')
    return {
        'status':'pass', 'kind':'version8_installed_output_static_peer', 'external_pins':original['external_pins'],
        'continuation_pins':PINS,
        'role_disclosure':'Author of narrow v4 external release-helper reference-count correction; root independently reviewed that helper. This installed-output/raw-log check does not independently review the author implementation.',
        'basis_sources':110, 'runtime_sources':111, 'package_modules':20,
        'reference_files_total':40, 'reference_closure_files':38, 'authenticated_reference_documents':2,
        'upstream_authenticated_files':35, 'source_bytes_verified':True, 'source_stable_during_peer':True,
        'document_overrides':2, 'prospective_metadata_additions':1,
        'own_venv':True, 'version':'0.4.1.dev0', 'user_site':False,
        'recorded_phases_verified':6, 'recorded_unittest_test_starts':276,
        'recorded_unittest_success_completions':276, 'interleaved_warning_tests':multiline,
        'recorded_protected_source_maps_equal':True, 'protected_map_entries':417,
        'protected_source_bodies_reopened':0, 'validation_guard':guard,
        'peer_guard':{'initial_counts':original['peer_guard']['counts'], 'finish_counts':dict(COUNTS),
            'scope':'Fixed explicit metadata/source/log reads; no directory discovery, helper/package import, process or network. Python hook is not an OS-wide guard.'},
        'new_test_or_cli_runs':0, 'new_environments':0, 'new_actual_providers_or_cpu_research':0,
        'private_owner_reads':0, 'git_or_publication_actions':0, 'findings':[],
        'initial_peer_failure_preserved':True,
        'initial_failure_cause':'External peer parser assumed one-line ... ok; upstream parse SyntaxWarning interleaved one existing passing test. Root environment/source was not the cause.',
        'continuation_only':'Fixed raw completion parser plus previously unvisited guard and source post-audit drift checks; six successful root phases never rerun.',
        'limitations':[
            'Prior completed metadata/runtime/closure checks use the immutable initial reviewer execution, source and raw input hashes.',
            'Old protected417 unchanged is a before/after metadata consistency check; this peer did not open their original bodies.',
            'Validation hook does not cover one allowed tiny CPU child and is not an OS-wide or all-sibling read proof.',
            'No authentication or provider access was attempted or proved; recorded zero-action scope is corroborated by fixed commands/guard.',
            'Engineering installation and test success does not prove research improvement or complete the Goal.',
        ],
    }

if __name__ == '__main__':
    try:
        result = main()
    except BaseException as error:
        result = {'status':'failed', 'kind':'version8_installed_output_static_peer_continuation',
            'failure':{'type':type(error).__name__, 'message':str(error)}, 'continuation_pins':PINS,
            'peer_guard':{'finish_counts':dict(COUNTS)}, 'new_test_or_cli_runs':0}
    result['finish_read_inventory'] = dict(READS)
    with (HERE/'complete-result.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'finish_read_inventory'}, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'pass' else 1)
