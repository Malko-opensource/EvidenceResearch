"""Freeze a public synthetic CSV evaluator before the independent skill demonstration."""
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from research_cli.core import Store, sha256_file

WORKSPACE = (PROJECT / 'research-workspaces/goal-plugin-demo-20261004').resolve()
CSV = 'team,rating\nA,5\nA,3\nA,\nB,4\nB,5\nB,1\n'
VALIDATOR = '''import csv,io,json,math,sys
from pathlib import Path
bundle=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
rows=list(csv.DictReader(io.StringIO('team,rating\\nA,5\\nA,3\\nA,\\nB,4\\nB,5\\nB,1\\n')))
values=[float(r['rating']) for r in rows if r['rating'].strip()]
expected=sum(values)/len(values)/5*100
groups={}
for r in rows:
    if r['rating'].strip():groups.setdefault(r['team'],[]).append(float(r['rating']))
means={k:sum(v)/len(v) for k,v in groups.items()}
observed=json.loads(Path(bundle['artifacts']['summary']).read_text(encoding='utf-8'))
matches=(observed.get('valid_rows')==len(values) and observed.get('missing_rows')==len(rows)-len(values)
    and math.isclose(observed.get('satisfaction_pct',-999),expected,abs_tol=1e-9)
    and isinstance(observed.get('team_means'),dict) and set(observed['team_means'])==set(means)
    and all(math.isclose(observed['team_means'][k],v,abs_tol=1e-9) for k,v in means.items()))
print(json.dumps({'metrics':{'satisfaction_pct':observed.get('satisfaction_pct',-999),'calculation_matches':float(matches)},
 'details':{'expected_satisfaction_pct':expected,'expected_valid_rows':len(values),'expected_missing_rows':len(rows)-len(values),
 'expected_team_means':means,'scope':'public synthetic fixed CSV; no population inference','fixed_input_replications':True}}))
'''

def main():
    assert WORKSPACE.is_relative_to((PROJECT/'research-workspaces').resolve())
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for name, text in [('data.csv', CSV), ('fixed_validator.py', VALIDATOR)]:
        path = WORKSPACE/name
        if path.exists() and path.read_text(encoding='utf-8') != text:
            raise RuntimeError('Existing demonstration source differs: '+str(path))
        path.write_text(text, encoding='utf-8')
    initialized = Store.init(WORKSPACE)
    store = Store(WORKSPACE)
    result = store.validator_register('csv-owner-fixed-v1', [store.runner_interpreter(), str(WORKSPACE/'fixed_validator.py'), '{bundle}'],
                                      store.owner_key_path.read_text(encoding='utf-8').strip())
    report = {'purpose':'development skill/channel demonstration; not research performance', 'workspace':WORKSPACE.name,
              'csv_sha256':sha256_file(WORKSPACE/'data.csv'), 'validator_source_sha256':sha256_file(WORKSPACE/'fixed_validator.py'),
              'validator':result, 'business_threshold':80, 'repeat_fixture_seeds':[0,1,2],
              'repeat_rationale':'three fixed-input executions exercise descriptive distribution, not independent sampling or power',
              'recorded_before_execution':not store.status()['registrations'], 'revision':store.revision()}
    output = PROJECT/'validation/research-report-0.8.0/demo-setup.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        previous=json.loads(output.read_text(encoding='utf-8'))
        if previous['csv_sha256'] != report['csv_sha256'] or previous['validator_source_sha256'] != report['validator_source_sha256']:
            raise RuntimeError('Prior frozen fixture differs')
    else:
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('workspace','csv_sha256','validator_source_sha256','revision')},ensure_ascii=False))

if __name__=='__main__':main()
