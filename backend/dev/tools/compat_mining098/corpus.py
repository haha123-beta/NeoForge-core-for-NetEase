"""Explicit, reproducible Modrinth acquisition; downloaded bytecode is never run."""
from pathlib import Path
import hashlib,json,time,urllib.parse,urllib.request,urllib.error,subprocess,shutil,threading,concurrent.futures
from .engine import save,load,digest

API='https://api.modrinth.com/v2'
HEADERS={'User-Agent':'NeoCore-CompatibilityMining/0.9.8 (local static research)'}
_lock=threading.Lock()
_last=0

def request(url):
    global _last
    with _lock:
        delay=.3-(time.monotonic()-_last)
        if delay>0:time.sleep(delay)
        _last=time.monotonic()
    curl=shutil.which('curl.exe')
    if curl:
        p=subprocess.run([curl,'--globoff','--silent','--show-error','--fail','--max-time','60','--retry','2','--retry-delay','3','--user-agent',HEADERS['User-Agent'],url],capture_output=True)
        if p.returncode:raise OSError('Download failed: '+p.stderr.decode('utf-8',errors='replace')[:300])
        return p.stdout
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=60) as r:return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429,502,503,504) or attempt==3:raise
            time.sleep(min(30,int(e.headers.get('Retry-After','5'))))
        except (TimeoutError,urllib.error.URLError):
            if attempt==3:raise
            time.sleep(2)

def fetch(output,count=100,max_mb=20,progress=print):
    if not 1<=count<=500:raise ValueError('Count must be 1..500')
    if not 1<=max_mb<=512:raise ValueError('Size limit must be 1..512 MiB')
    output=Path(output);output.mkdir(parents=True,exist_ok=True);jars=output/'jars';jars.mkdir(exist_ok=True)
    manifest=output/'corpus.json'
    data=load(manifest) if manifest.exists() else dict(schema_version=1,source='Modrinth API v2',game_version='1.21.1',loader='neoforge',selection='downloads descending; latest matching version; bounded primary JAR',artifacts=[],skipped=[])
    valid=[]
    for row in data['artifacts']:
        p=Path(row['path'])
        if p.is_file() and digest(p)==row['sha256']:valid.append(row)
        else:data['skipped'].append(dict(project_id=row['project_id'],error='Previously fetched artifact missing or changed'))
    data['artifacts']=valid
    known={r['project_id'] for r in data['artifacts']};offset=0
    facets=json.dumps([['project_type:mod'],['categories:neoforge'],['versions:1.21.1']])
    while len(data['artifacts'])<count:
        url=API+'/search?'+urllib.parse.urlencode(dict(facets=facets,index='downloads',limit=100,offset=offset))
        search=json.loads(request(url));hits=search['hits']
        if not hits:break
        def one(hit):
            project=hit['project_id']
            page='https://modrinth.com/mod/'+hit['slug']
            try:
                url=API+'/project/'+urllib.parse.quote(project,safe='')+'/version?'+urllib.parse.urlencode(dict(loaders='["neoforge"]',game_versions='["1.21.1"]',include_changelog='false'))
                versions=json.loads(request(url));time.sleep(.25)
                versions=sorted(versions,key=lambda v:v['date_published'],reverse=True)
                selected=None
                for v in versions:
                    if 'neoforge' not in v['loaders'] or '1.21.1' not in v['game_versions']:continue
                    files=[f for f in v['files'] if f['filename'].lower().endswith('.jar') and f['size']<=max_mb*1024*1024]
                    if files:selected=(v,sorted(files,key=lambda f:not f.get('primary',False))[0]);break
                if not selected:raise ValueError('No matching JAR within size limit')
                v,f=selected;u=urllib.parse.urlsplit(f['url'])
                if u.scheme!='https' or u.hostname!='cdn.modrinth.com':raise ValueError('Unexpected artifact origin')
                if not f['hashes'].get('sha512'):raise ValueError('Missing publisher SHA512')
                raw=request(f['url'])
                if len(raw)!=f['size'] or len(raw)>max_mb*1024*1024:raise ValueError('Artifact size mismatch')
                if hashlib.sha512(raw).hexdigest()!=f['hashes']['sha512']:raise ValueError('Artifact hash mismatch')
                sha=hashlib.sha256(raw).hexdigest();path=jars/(project+'-'+sha[:12]+'.jar')
                path.write_bytes(raw)
                return True,dict(project_id=project,title=hit['title'],slug=hit['slug'],project_url=page,version_id=v['id'],version=v['version_number'],published=v['date_published'],original_filename=f['filename'],file_url=f['url'],bytes=len(raw),sha512=f['hashes']['sha512'],sha256=sha,path=str(path.resolve()),dependencies=v.get('dependencies',[]))
            except (ValueError,OSError,KeyError) as e:
                return False,dict(project_id=project,url=page,error=type(e).__name__+': '+str(e))
        pending=[hit for hit in hits if hit['project_id'] not in known][:count-len(data['artifacts'])]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for future in concurrent.futures.as_completed([pool.submit(one,hit) for hit in pending]):
                ok,row=future.result()
                if ok:
                    data['artifacts'].append(row);known.add(row['project_id']);progress(str(len(known))+'/'+str(count)+' '+row['slug'])
                else:data['skipped'].append(row)
                save(manifest,data)
        offset+=len(hits)
        if offset>=search['total_hits']:break
    data['status']='FETCHED' if len(data['artifacts'])>=count else 'PARTIAL';data['requested']=count
    data['sampling_limit']='Popularity-biased convenience sample, not a random or ecosystem-wide compatibility estimate. No JAR is executed or redistributed by this command.'
    save(manifest,data);return dict(status=data['status'],artifacts=len(data['artifacts']),manifest=str(manifest))
