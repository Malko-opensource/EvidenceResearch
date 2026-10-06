"""Owner preparation only; model calls are dispatched by the external framework."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_cli.core import Store, sha256_file
from research_cli.runner import run, verify


def seed_prior(store, episode):
    directory = episode/'prior'
    directory.mkdir()
    task_directory = Path(__file__).parent/'tasks'/'M_PRIOR'
    for name in ('solution.py', 'input.csv'):
        shutil.copyfile(task_directory/name, directory/name)
    shutil.copyfile(Path(__file__).with_name('task.py'), directory/'task.py')
    goal = store.goal_create('Prior event correction experiment', 'Separate earlier failed task; excluded from final evaluation')
    hypothesis = store.hypothesis_create(goal['id'], 'Full-row equality can remove repeated measurement events.')
    spec = {'hypothesis_id': hypothesis['id'], 'change': 'Deduplicate measurement events by full-row equality',
            'comparison': 'Required latest valid row per event_id, with later-input tie break',
            'data_split': {'development': 'M_PRIOR separate fixture', 'evaluation': 'M_PRIOR fixed independent cases'},
            'seed': 0, 'source_version': {'label': 'prior-full-row-v1', 'files': {
                name: sha256_file(directory/name) for name in ('solution.py', 'input.csv', 'task.py')}},
            'metrics': ['pass_rate'], 'criteria': [{'metric': 'pass_rate', 'op': '>=', 'threshold': 1.0}],
            'command': [sys.executable, 'task.py', 'M_PRIOR'], 'cwd': str(directory),
            'artifacts': [{'name': name, 'path': name} for name in ('solution.py', 'input.csv', 'result.json', 'invocations.jsonl')],
            'validator': 'csv-fixed-v1', 'task_id': 'M_PRIOR', 'conditions': {'dependency_policy': 'standard library'}}
    registration = store.register(goal['id'], spec, 'prior-register')['registration']
    run(store, registration['id'], 'prior-run')
    outcome = verify(store, registration['id'])['record']
    if outcome['verification']['state'] != 'failed':
        raise RuntimeError('Prior must actually fail fixed validation')
    store.decide(registration['id'], 'rejected',
                 'Full-row equality preserves corrected duplicates of one event_id. Applicable to event measurement data; use latest valid timestamp and later input on ties.')
    store.add_evidence(registration['id'], 'inference', 'Failure interpretation from fixed checks: row equality does not identify repeated event_id; this interpretation is distinct from verified measurements.')
    return registration['id']


def prepare(task_id, condition, episode):
    episode = Path(episode).resolve()
    if episode.exists():
        raise RuntimeError('Episode destination must be new')
    episode.mkdir(parents=True)
    source = Path(__file__).parent/'tasks'/task_id
    for name in ('BRIEF.ko.md', 'solution.py', 'input.csv'):
        shutil.copyfile(source/name, episode/name)
    shutil.copyfile(Path(__file__).with_name('task.py'), episode/'task.py')
    metadata = {'task_id': task_id, 'condition': condition, 'prepared_at': datetime.now(timezone.utc).isoformat(),
                'initial_hashes': {name: sha256_file(episode/name) for name in ('BRIEF.ko.md','solution.py','input.csv','task.py')},
                'criteria': [{'metric': 'pass_rate', 'op': '>=', 'threshold': 1.0}],
                'fixed_validator_sha256': sha256_file(Path(__file__).with_name('fixed_validator.py')),
                'framework': 'Codex fresh subagent', 'model': 'inherited parent; exact identifier unknown',
                'external_tokens': {'status': 'unknown', 'value': None}}
    if condition != 'B':
        initialized = Store.init(episode/'research')
        store = Store(episode/'research')
        store.validator_register('csv-fixed-v1', [sys.executable, str(Path(__file__).with_name('fixed_validator.py').resolve()), '{bundle}'],
                                 Path(initialized['owner_key_path']).read_text(encoding='utf-8').strip())
        metadata['research_workspace'] = str(store.root)
        if condition == 'C_ON':
            metadata['prior_registration'] = seed_prior(store, episode)
    (episode/'episode.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True)
    parser.add_argument('--condition', choices=['B','C_OFF','C_ON'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    prepare(args.task, args.condition, args.output)
