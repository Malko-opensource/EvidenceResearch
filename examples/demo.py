"""Library example; identical state rules to the CLI. Use a new workspace."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research_cli.core import Store, sha256_file
from research_cli.runner import run, verify

root = Path(sys.argv[1]).resolve()
initialized = Store.init(root)
store = Store(root)
goal_result = store.goal_create('Verify a simple mean', 'Development-only example')
goal = goal_result.get('goal', goal_result)
goal_id = goal['id']
hyp_result = store.hypothesis_create(goal_id, 'The registered computation agrees with an independent recomputation.')
hypothesis = hyp_result.get('hypothesis', hyp_result)
code_dir = root/'experiment'
code_dir.mkdir()
source = Path(__file__).with_name('local_task.py')
expected = sha256_file(source)
store.validator_register('mean-v1', [sys.executable, str(Path(__file__).with_name('local_validator.py').resolve()), '{bundle}'],
                         Path(initialized['owner_key_path']).read_text(encoding='utf-8').strip())
spec = {'hypothesis_id': hypothesis['id'], 'change': 'Arithmetic mean', 'comparison': 'Independent stdlib recomputation',
        'data_split': {'train': 'none', 'evaluation': 'fixed four values'}, 'seed': 0,
        'source_version': {'label': 'mean-v1', 'files': {'task.py': expected}},
        'metrics': ['correct'], 'criteria': [{'metric': 'correct', 'op': '>=', 'threshold': 1}],
        'command': [sys.executable, 'task.py'], 'cwd': str(code_dir),
        'artifacts': [{'name': 'result', 'path': 'result.json'}], 'validator': 'mean-v1'}
registration = store.register(goal_id, spec, 'mean-register')['registration']
# The final implementation is placed only after the source hash is preregistered.
shutil.copyfile(source, code_dir/'task.py')
execution = run(store, registration['id'], 'mean-execute')
verification = verify(store, registration['id'])
decision = store.decide(registration['id'], 'adopted', 'Fixed verifier recomputed the preserved values.')
print(json.dumps({'execution': execution, 'verification': verification, 'decision': decision}, ensure_ascii=False))
