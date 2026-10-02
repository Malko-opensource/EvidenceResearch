"""One whole-suite check of the separately frozen c8 engineering source."""
from pathlib import Path
import ast,hashlib,json,os,re,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'work/c8'
OUTPUT=ROOT/'work/c8-whole-check-v2'
EXPECTED_SOURCE='6fce28fb5ed196717011906b9071091244f72bd7874728f2114cb399d2468d69'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    manifest=ROOT/'work/c8-implementation-v1/source-manifest.json'
    if sha(manifest)!=EXPECTED_SOURCE:raise ValueError('External c8 held source pin differs')
    m=json.loads(manifest.read_text(encoding='utf-8'));before={r['relative']:r['sha256'] for r in m['files']}
    if len(before)!=110 or any(sha(CANDIDATE/name)!=digest for name,digest in before.items()):raise ValueError('Candidate differs from held110')
    original=json.loads((ROOT/'work/c8-source-copy-v1.json').read_text(encoding='utf-8'))
    if sha(ROOT/'work/c8-source-copy-v1.json')!='1ab2da19edbadff413042af0f3441377ebe41c70f9cf6a0e5e23c8bd14f9eb30':raise ValueError('Frozen original source pin differs')
    protected={('versions/v7-development/'+r['relative']):r['sha256'] for r in original['files']}
    old=json.loads((ROOT/'work/c7-independent-validation-v1/frozen-source-before.json').read_text(encoding='utf-8'))
    if old['file_count']!=309 or len(old['files'])!=309:raise ValueError('Unexpected old source inventory')
    protected.update({r['path']:r['sha256'] for r in old['files']})
    if any(sha(ROOT/name)!=digest for name,digest in protected.items()):raise ValueError('Protected prior source changed')
    if OUTPUT.exists():raise FileExistsError('Preserve old whole proof')
    OUTPUT.mkdir();snapshot=OUTPUT/'s'
    for name in before:
        p=snapshot/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CANDIDATE/name,p)
    shutil.copyfile(__file__,OUTPUT/'reproduce.source.py')
    write(OUTPUT/'before.json',{'candidate':before,'protected':protected,'manifest_sha256':EXPECTED_SOURCE})
    old_helper=ROOT/'evaluation/validate_c7_candidate.py'
    assignments=[n for n in ast.parse(old_helper.read_text(encoding='utf-8')).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GUARD' for t in n.targets)]
    if len(assignments)!=1:raise ValueError('Original guard literal is ambiguous')
    guard=ast.literal_eval(assignments[0].value)
    guard=guard.replace('Externally controlled c7 engineering guard','Externally controlled c8 engineering guard')
    guard=guard.replace('if event=="open" and isinstance(args[0],(str,bytes)):', 'if event in ("open","os.listdir","os.scandir") and args and isinstance(args[0],(str,bytes)):')
    guard=guard.replace('parts[0]=="tf"', 'parts[0] in ("tf","hf")')
    guard_dir=OUTPUT/'audit_guard';guard_dir.mkdir();(guard_dir/'sitecustomize.py').write_text(guard,encoding='utf-8')
    temporary=ROOT.parent/'_t8whole2'
    if temporary.exists():raise FileExistsError('Preserve prior short synthetic output')
    temporary.mkdir()
    names=('SystemRoot','WINDIR','COMSPEC','PATHEXT','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','USERPROFILE','LOCALAPPDATA','APPDATA')
    env={name:os.environ[name] for name in names if name in os.environ}
    windows=env.get('SystemRoot',r'C:\Windows')
    env.update(PATH=os.pathsep.join((str(Path(sys.executable).parent),windows,str(Path(windows)/'System32'))),
      PYTHONPATH=str(guard_dir),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',PYTHONNOUSERSITE='1',
      TEMP=str(temporary),TMP=str(temporary),ER_RELEASE_ROOT=str(CANDIDATE),ER_PROJECT_ROOT=str(ROOT),
      ER_PROOF_ROOT=str(OUTPUT),ER_FIXTURE_TMP=str(temporary),ER_AUDIT_GUARD_PATH=str(OUTPUT/'unit-guard.json'))
    command=[sys.executable,'-X','utf8','-B','-m','unittest','discover','-s','tests','-v']
    started=time.monotonic()
    with (OUTPUT/'stdout.log').open('xb') as out,(OUTPUT/'stderr.log').open('xb') as err:
        process=subprocess.run(command,cwd=CANDIDATE,env=env,stdout=out,stderr=err)
    elapsed=time.monotonic()-started
    after={name:sha(CANDIDATE/name) for name in before};old_after={name:sha(ROOT/name) for name in protected}
    write(OUTPUT/'after.json',{'candidate':after,'protected':old_after})
    log=(OUTPUT/'stderr.log').read_text(encoding='utf-8');match=re.search(r'Ran (\d+) tests in',log)
    audit=json.loads((OUTPUT/'unit-guard.json').read_text(encoding='utf-8')) if (OUTPUT/'unit-guard.json').exists() else None
    valid=bool(process.returncode==0 and match and int(match.group(1))==276 and before==after and protected==old_after and audit
      and not any(v for k,v in audit['counts'].items() if k!='allowed_cpu_fixture_subprocesses'))
    result={'kind':'c8_frozen_whole_engineering_suite','valid':valid,'source_manifest_sha256':EXPECTED_SOURCE,
      'checks':int(match.group(1)) if match else None,'declared_expected_tests':276,'exit_code':process.returncode,'seconds':elapsed,
      'command':command,'cwd':str(CANDIDATE),'source_snapshot':'s','candidate110_unchanged':before==after,
      'protected_source_files':len(protected),'protected_sources_unchanged':protected==old_after,'guard':audit,
      'guard_sha256':sha(guard_dir/'sitecustomize.py'),'guard_basis_source_sha256':sha(old_helper),
      'logs':{n:sha(OUTPUT/n) for n in ('stdout.log','stderr.log')},'inherited_credentials_copied':False,
      'actual_models_or_research_trials':0,'trusted_cpu_unit_fixture_child':'Explicit deterministic tiny CPU fixture; parent hook is not a global OS or child read proof',
      'independent_ten_families_completed_by_this_suite':False,'new_environment_installation_validated':False,
      'framework_improvement_proven':False,'goal_complete':False}
    write(OUTPUT/'result.json',result)
    print(json.dumps({k:result[k] for k in ('valid','checks','exit_code','seconds','candidate110_unchanged','protected_sources_unchanged')}))
    return 0 if valid else 1
if __name__=='__main__':raise SystemExit(main())
