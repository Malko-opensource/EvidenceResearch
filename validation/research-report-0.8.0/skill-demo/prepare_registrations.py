import json
from pathlib import Path

out = Path(__file__).resolve().parent
project = out.parents[2]
manifest = json.loads((out/'source-manifest.json').read_text(encoding='utf-8'))
for seed in (0, 1, 2):
    spec = {
        'hypothesis_id': 'hyp_60947ff54c8e423f9a66f13c1f5d8fa3',
        'change': 'External agent CSV summary under supplied missing-exclusion rule; one deterministic source for all prescribed functional replications',
        'comparison': 'Frozen owner independent recalculation of fixed fixture and supplied overall 80% business criterion; no performance baseline',
        'data_split': {'development': 'all rows of supplied public synthetic data.csv', 'evaluation': 'same pinned input, independently implemented owner frozen validator; no independent population or holdout inference'},
        'seed': seed,
        'source_version': {'label': manifest['label'], 'files': manifest['files']},
        'metrics': ['calculation_matches','satisfaction_pct'],
        'criteria': [{'metric': 'calculation_matches','op': '==','threshold': 1},{'metric': 'satisfaction_pct','op': '>=','threshold': 80}],
        'conditions': {'repeat_design': 'three_fixed_input_replications','input': 'same fixed public synthetic data.csv','missing_rule': 'empty rating counted and excluded','rating_range': '1-5','satisfaction_formula': 'mean_valid_rating/5*100','unit': 'percentage','stochastic_sampling': False,'scope': 'fixed fixture descriptive summary only'},
        'command': [str(project/'.mcp-venv'/'Scripts'/'python.exe'),'task.py','--seed',str(seed)],
        'cwd': manifest['experiment_cwd'],
        'artifacts': [{'name': 'summary','path': 'summary.json'}],
        'validator': 'csv-owner-fixed-v1'
    }
    (out/f'preregistration.seed{seed}.json').write_text(json.dumps(spec,indent=2)+'\n',encoding='utf-8')
