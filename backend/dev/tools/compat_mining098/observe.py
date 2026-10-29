"""Run actual conversion observations without treating static suspicions as errors."""
from pathlib import Path
import importlib.util,json,os,subprocess,sys,time,urllib.parse
from .engine import load,save,digest

def observe(run,backend,output):
    root=Path(run)
    if (root/'cohort.json').exists():
        run=load(root/'cohort.json')
        if digest(root/'run.json')!=run['run_sha256']:raise ValueError('Cohort no longer matches raw scan evidence')
    else:run=load(root/'run.json')
    backend=Path(backend).resolve();output=Path(output)
    if not (backend/'cli.py').is_file():raise ValueError('Expected a GUI/CLI backend directory')
    output.mkdir(parents=True,exist_ok=False);work=output/'private_workspace'
    spec=importlib.util.spec_from_file_location('_nc_mining_observation_cli',backend/'cli.py');cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    env=dict(os.environ,TEMP=str(output/'tmp'),TMP=str(output/'tmp'));(output/'tmp').mkdir()
    subprocess.run([sys.executable,'-B',str(backend/'cli.py'),'--data-dir',str(work),'--json','start'],check=True,capture_output=True,env=env)
    results=[];active=None
    try:
        for a in run['artifacts']:
            if not a.get('metadata'):continue
            p=Path(a['path']);assert digest(p)==a['sha256'],'Input no longer matches scan'
            job=cli.call(work,'api/import',p.read_bytes(),{'X-Filename':urllib.parse.quote(p.name)})['job'];active=job['id']
            job=cli.call(work,'api/export',json.dumps({'id':active}).encode())['job'];deadline=time.monotonic()+900
            while job['status'] in ('QUEUED','RUNNING'):
                if time.monotonic()>deadline:
                    cli.call(work,'api/cancel',json.dumps({'id':active}).encode());raise TimeoutError('Conversion observation exceeded 900 seconds')
                time.sleep(.5);job=cli.call(work,'api/job/'+active)['job']
            report=cli.call(work,'api/report/'+active);target=output/'reports'/(a['sha256']+'_report.json');save(target,report)
            save(output/'diagnostics'/(a['sha256']+'.json'),cli.call(work,'api/diagnostic/'+active))
            assert digest(p)==a['sha256'],'Input changed during observation'
            row=dict(artifact_sha256=a['sha256'],name=p.name,status=job['status'],report=str(target),translation=report.get('result',{}).get('translation'),engine_verified=False)
            results.append(row);save(output/'observations.json',results);print(json.dumps(row,ensure_ascii=True),flush=True);active=None
    finally:
        if active:
            cli.call(work,'api/cancel',json.dumps({'id':active}).encode())
            end=time.monotonic()+30
            while time.monotonic()<end and cli.call(work,'api/job/'+active)['job']['status'] in ('QUEUED','RUNNING'):time.sleep(.2)
        cli.call(work,'api/shutdown',b'{}')
    return dict(status='OBSERVATIONS_RECORDED',artifacts=len(results),reports=str(output/'reports'),engine_verified=False)
