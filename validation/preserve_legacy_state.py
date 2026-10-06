"""Back up existing web workspaces and compare original research rows after compatible migration."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

PROJECT=Path(__file__).resolve().parents[1]
OUTPUT=PROJECT/'validation/research-report-0.8.0/legacy-preservation'
TABLES=('goals','hypotheses','registrations','validators','runs','evidence','verifications','decisions','requests','events')

def rows(database):
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as conn:
        names={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        data={name:[list(row) for row in conn.execute('SELECT * FROM '+name+' ORDER BY 1')]
              for name in TABLES if name in names}
        return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    manifest=OUTPUT/'manifest.json'
    if not args.check:
        if manifest.exists():raise RuntimeError('Existing preservation manifest is immutable')
        report={}
        for path in (PROJECT/'research-workspaces').glob('*/.research/state.sqlite3'):
            name=path.parent.parent.name
            backup=OUTPUT/(name+'.sqlite3')
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as source, sqlite3.connect(backup) as target:
                source.backup(target)
            data=rows(backup.resolve())
            report[name]={'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
                          'tables':{table:hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
                                    for table,values in data.items()},'run_count':len(data.get('runs',[]))}
        manifest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'ok':True,'backed_up':len(report),'original_runs':sum(v['run_count'] for v in report.values())}))
    else:
        report=json.loads(manifest.read_text(encoding='utf-8'));invalid=[]
        for name,original in report.items():
            data=rows((PROJECT/'research-workspaces'/name/'.research/state.sqlite3').resolve())
            for table,digest in original['tables'].items():
                actual=hashlib.sha256(json.dumps(data.get(table),sort_keys=True).encode()).hexdigest()
                if actual!=digest:invalid.append({'workspace':name,'table':table})
        result={'ok':not invalid,'invalid':invalid,'original_workspaces':len(report)}
        (OUTPUT.parent/'legacy-state-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result));return int(bool(invalid))
    return 0
if __name__=='__main__':raise SystemExit(main())
