"""Record complete model-free functional checks for the reporting/plugin release."""
import json
from pathlib import Path
import re
import subprocess
import time

PROJECT=Path(__file__).resolve().parents[1]
OUTPUT=PROJECT/'validation/research-report-0.8.0'

def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    commands={'python':[str(PROJECT/'.mcp-venv/Scripts/python.exe'),'-X','utf8','-m','unittest','discover','-s','tests','-v'],
              'model':[r'C:\Program Files\nodejs\node.exe','--test','tests/test_view_model.mjs']}
    report={}
    for name,command in commands.items():
        started=time.monotonic()
        result=subprocess.run(command,cwd=PROJECT,capture_output=True,text=True,encoding='utf-8',
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        output=result.stdout+result.stderr
        (OUTPUT/(name+'-tests.log')).write_text(output,encoding='utf-8')
        count=re.search(r'Ran (\d+) tests',output) if name=='python' else re.search(r'tests (\d+)',output)
        report[name]={'ok':result.returncode==0,'returncode':result.returncode,'command':command,
                      'count':int(count.group(1)) if count else None,'elapsed_seconds':time.monotonic()-started}
        print(json.dumps({name:report[name]},ensure_ascii=False),flush=True)
    (OUTPUT/'test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(any(not result['ok'] for result in report.values()))
if __name__=='__main__':raise SystemExit(main())
