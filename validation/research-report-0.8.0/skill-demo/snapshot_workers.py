import datetime
import hashlib
import json
import sys
from pathlib import Path

out = Path(__file__).resolve().parent
project = out.parents[2]
runs_path = project/'research-workspaces'/'goal-plugin-demo-20261004'/'.research'/'runs'
records = []
for path in sorted(runs_path.iterdir()):
    if not path.is_dir():
        continue
    files = {name:{'sha256':hashlib.sha256((path/name).read_bytes()).hexdigest(),'bytes':(path/name).stat().st_size} for name in ('launch.json','process.json','receipt.json') if (path/name).is_file()}
    process = json.loads((path/'process.json').read_text(encoding='utf-8')) if (path/'process.json').is_file() else None
    records.append({'run_id':path.name,'files':files,'process':process})
snapshot = {'label':sys.argv[1],'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_directory_count':len(records),'runs':records}
(out/f'workers-{sys.argv[1]}.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
print(json.dumps(snapshot))
