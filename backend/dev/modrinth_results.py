"""Append-only frozen-sample evidence ledger. Local checks never manufacture engine results."""
import argparse
import ast
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import zipfile
from modrinth_benchmark import encoded, sha, save, timestamp

STATUSES={'NOT_RUN','BLOCKED_SOURCE','BLOCKED_DEPENDENCY','BLOCKED_TRANSLATION','BLOCKED_RUNTIME',
          'READY_LOCAL','FAIL_ENGINE','PARTIAL_ENGINE','PASS_ENGINE'}
ENGINE={'FAIL_ENGINE','PARTIAL_ENGINE','PASS_ENGINE'}
CHECKS={'startup','persistence','side_sync','unload','stability'}


def check_distribution(path,report):
    """Match protocol-2 game source bytes to validation, without executing snapshot Python."""
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        snapshots=[n for n in names if n.endswith('/NeoCoreSourceScripts/source_snapshot.py')]
        if len(names)!=len(set(names)) or len(snapshots)!=1 or archive.testzip() is not None:
            raise ValueError('Distribution requires one intact protocol-2 core snapshot')
        snapshot=snapshots[0];tree=ast.parse(archive.read(snapshot).decode('utf-8-sig'))
        values=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BUNDLE' for t in n.targets)]
        if len(values)!=1 or not isinstance(values[0],ast.Call) or len(values[0].args)!=1:
            raise ValueError('Unrecognized source snapshot serialization')
        bundle=json.loads(ast.literal_eval(values[0].args[0]))
        if bundle.get('schema_version')!=1 or bundle.get('kind')!='neocore_core_sources' or not bundle.get('sources'):
            raise ValueError('Not a core source bundle')
        fingerprint=report['source_sha256']
        for name,record in bundle['sources'].items():
            raw=record['source'].encode('utf-8');digest=record['sha256']
            if digest not in (sha(raw),sha(b'\xef\xbb\xbf'+raw)) or fingerprint.get('NeoForgeCoreScripts/'+record['origin'])!=digest:
                raise ValueError('Distribution/validation source mismatch: '+name)
        prefix=snapshot[:-len('source_snapshot.py')]
        for name,key in [('source_modules.py','NeoForgeCoreScripts/core/source_modules.py'),
                         ('runtime_host.py','NeoForgeCoreScripts/core/runtime_host.py'),
                         ('modMain.py','dev/templates/source_core_modMain.py')]:
            if sha(archive.read(prefix+name))!=fingerprint.get(key):raise ValueError('Native bootstrap/validation mismatch: '+name)
        return {'core_modules':len(bundle['sources']),'core_snapshot_sha256':sha(archive.read(snapshot))}


class Ledger:
    def __init__(self, root):
        self.root=Path(root).resolve()
        frozen=json.loads((self.root/'samples.json').read_bytes())
        self.fingerprint=frozen['sample_sha256']
        if sha(encoded(frozen['samples']))!=self.fingerprint:
            raise ValueError('Frozen sample integrity failure')
        self.samples={r['sample_id']:r for r in frozen['samples']}
        if len(self.samples)!=len(frozen['samples']):raise ValueError('Duplicate sample identity')
        self.directory=self.root/'results'
        if self.directory.exists() and (self.directory.is_symlink() or self.directory.resolve().parent!=self.root):
            raise ValueError('Ledger directory escapes round')
        self.path=self.directory/'events.jsonl'

    def read(self):
        if not self.path.exists():return []
        if self.path.is_symlink():raise ValueError('Ledger file cannot be a link')
        events=[];previous='0'*64
        for raw in self.path.read_bytes().splitlines():
            event=json.loads(raw)
            digest=event.get('sha256');body={k:v for k,v in event.items() if k!='sha256'}
            if (event.get('number')!=len(events)+1 or event.get('previous_sha256')!=previous or
                event.get('sample_freeze_sha256')!=self.fingerprint or sha(encoded(body))!=digest):
                raise ValueError('Ledger hash chain/round mismatch; preserve file and restore from a verified copy')
            if event.get('sample_id') is not None:
                sample=self.samples.get(event['sample_id'])
                if sample is None or event.get('version_id')!=sample['version']['id']:
                    raise ValueError('Ledger sample/version differs from freeze')
            previous=digest;events.append(event)
        return events

    @contextmanager
    def locked(self):
        self.directory.mkdir(exist_ok=True)
        lock=self.directory/'writer.lock'
        descriptor=os.open(str(lock),os.O_WRONLY|os.O_CREAT|os.O_EXCL)
        try:yield
        finally:os.close(descriptor);lock.unlink()

    def append(self,kind,sample_id,payload,events):
        sample=self.samples[sample_id] if sample_id is not None else None
        event={'number':len(events)+1,'previous_sha256':events[-1]['sha256'] if events else '0'*64,
               'sample_freeze_sha256':self.fingerprint,'kind':kind,'sample_id':sample_id,
               'version_id':sample['version']['id'] if sample else None,
               'recorded_at':datetime.now(timezone.utc).isoformat(),'payload':payload}
        event['sha256']=sha(encoded(event))
        with self.path.open('ab') as stream:
            stream.write(encoded(event)+b'\n');stream.flush();os.fsync(stream.fileno())
        return event

    def sample(self,sample_id):
        if sample_id not in self.samples:raise ValueError('Not a frozen sample; custom demos cannot increase compatibility numerator')
        return self.samples[sample_id]

    def check_evaluation(self,sample,events):
        if sample['group']=='evaluation' and not any(e['kind']=='evaluation_freeze' for e in events):
            raise ValueError('Holdout work requires a frozen implementation first')

    def acceptance(self,sample_id,data):
        sample=self.sample(sample_id)
        with self.locked():
            events=self.read();self.check_evaluation(sample,events)
            cases=data.get('principal_cases')
            if not isinstance(cases,list) or not cases:raise ValueError('Freeze explicit principal cases before results')
            ids=[]
            for case in cases:
                if not all(isinstance(case.get(k),str) and case[k].strip() for k in ('id','steps','expected')):
                    raise ValueError('Principal cases require id, steps and expected behavior')
                ids.append(case['id'])
            if len(ids)!=len(set(ids)):raise ValueError('Duplicate principal case ID')
            digest=sha(encoded(data))
            old=[e for e in events if e['kind']=='acceptance' and e['sample_id']==sample_id]
            if old:
                if old[0]['payload']['acceptance_sha256']!=digest:raise ValueError('Acceptance is frozen; retain old round instead of weakening failed criteria')
                return old[0]
            if any(e['kind']=='result' and e['sample_id']==sample_id and e['payload']['status'] in ENGINE for e in events):
                raise ValueError('Cannot freeze acceptance after engine results')
            return self.append('acceptance',sample_id,{'acceptance_sha256':digest,'definition':data},events)

    def evidence(self,records):
        verified=[]
        for record in records:
            path=Path(record['path'])
            if path.is_absolute():raise ValueError('Evidence path must be relative to this round')
            absolute=(self.root/path).resolve()
            if self.root not in absolute.parents or not absolute.is_file() or absolute.stat().st_size==0:
                raise ValueError('Missing/empty/escaping evidence file: '+str(path))
            if any(parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()) for parent in [self.root/path]+list((self.root/path).parents) if parent!=self.root.parent):
                raise ValueError('Evidence links require an explicit copied artifact')
            digest=sha(absolute.read_bytes())
            if record.get('sha256') not in (None,digest):raise ValueError('Evidence SHA differs: '+str(path))
            verified.append(dict(record,sha256=digest))
        return verified

    def result(self,sample_id,data):
        sample=self.sample(sample_id)
        with self.locked():
            events=self.read();status=data.get('status')
            if status not in STATUSES:raise ValueError('Unknown sample status')
            if status!='NOT_RUN':self.check_evaluation(sample,events)
            if not isinstance(data.get('reason'),str) or not data['reason'].strip():raise ValueError('Reason required')
            payload=dict(data);payload['evidence']=self.evidence(data.get('evidence',[]))
            if status in ENGINE:
                accept=[e for e in events if e['kind']=='acceptance' and e['sample_id']==sample_id]
                if not accept:raise ValueError('No prior frozen acceptance')
                expected=accept[0]['payload']['acceptance_sha256']
                if data.get('acceptance_sha256')!=expected:raise ValueError('Wrong acceptance definition')
                run=data.get('engine_run',{})
                if run.get('environment')!='netease_pc' or not all(isinstance(run.get(k),str) and run[k].strip() for k in ('operator','observed_at','core_version','tool_version')):
                    raise ValueError('Engine observations require operator, time, core/tool and NetEase PC environment')
                timestamp(run['observed_at'])
                if sample['group']=='evaluation':
                    freeze=next(e['payload'] for e in events if e['kind']=='evaluation_freeze')
                    if any(run.get(k)!=freeze[k] for k in ('core_version','tool_version','distribution_sha256')):
                        raise ValueError('Holdout result used a different frozen implementation')
                if not payload['evidence']:raise ValueError('Engine status requires archived evidence; local tests do not qualify')
                if not any(r.get('kind') in ('engine_log','screenshot','video','manual_observation') for r in payload['evidence']):
                    raise ValueError('Local build metadata alone is not engine evidence')
                principal=data.get('principal_results',{})
                ids={c['id'] for c in accept[0]['payload']['definition']['principal_cases']}
                if set(principal)!=ids or any(v not in ('pass','fail','not_run') for v in principal.values()):raise ValueError('Every frozen principal case must be accounted for')
                checks=data.get('checks',{})
                if set(checks)!=CHECKS:raise ValueError('All applicable general checks must be accounted for')
                for key,value in checks.items():
                    if not isinstance(value,dict) or value.get('status') not in ('pass','fail','not_run','not_applicable'):raise ValueError('Invalid general check')
                    if value['status']=='not_applicable' and (key in ('startup','unload','stability') or not value.get('reason')):raise ValueError('Invalid/unexplained not-applicable check')
                passed=all(v=='pass' for v in principal.values()) and all(v['status'] in ('pass','not_applicable') for v in checks.values())
                if status=='PASS_ENGINE' and not passed:raise ValueError('Partial/unexecuted/failed major behavior cannot be a pass')
                if status=='PARTIAL_ENGINE' and (passed or checks['stability']['status']=='fail'):raise ValueError('Partial status conflicts with full pass or major stability failure')
                payload['evidence_scope']='Manual recorded engine observations; integrity checks are not automatic authentication of gameplay.'
            elif data.get('engine_run') is not None:
                raise ValueError('Do not attach engine attestation to a local/blocked status')
            return self.append('result',sample_id,payload,events)

    def freeze_evaluation(self,core_version,tool_version,distribution,validation_report):
        report_path=Path(validation_report);report=json.loads(report_path.read_bytes())
        if report.get('status')!='PASSED' or report.get('changed_during_run') or not report.get('source_sha256'):
            raise ValueError('Freeze requires passed validation with a stable source fingerprint')
        artifact=Path(distribution)
        if not artifact.is_file():raise ValueError('Missing distribution')
        if not core_version or not tool_version:raise ValueError('Implementation version labels required')
        match=check_distribution(artifact,report)
        payload={'core_version':core_version,'tool_version':tool_version,'distribution_sha256':sha(artifact.read_bytes()),
                 'validation_report_sha256':sha(report_path.read_bytes()),'source_fingerprint_sha256':sha(encoded(report['source_sha256'])),
                 'distribution_source_match':match}
        with self.locked():
            events=self.read();old=[e for e in events if e['kind']=='evaluation_freeze']
            if old:
                if old[0]['payload']!=payload:raise ValueError('Implementation already frozen; fixes require a separately reported round')
                return old[0]
            return self.append('evaluation_freeze',None,payload,events)

    def summary(self,group='evaluation'):
        with self.locked():events=self.read()
        latest={e['sample_id']:e['payload'] for e in events if e['kind']=='result'}
        rows=[dict(sample_id=sid,project_id=s['project_id'],version_id=s['version']['id'],status=latest.get(sid,{}).get('status','NOT_RUN'))
              for sid,s in self.samples.items() if s['group']==group]
        counts={status:sum(r['status']==status for r in rows) for status in sorted(STATUSES)}
        n=len(rows);p=counts['PASS_ENGINE'];f=counts['FAIL_ENGINE']+counts['PARTIAL_ENGINE']
        b=sum(counts[k] for k in counts if k.startswith('BLOCKED_'));u=counts['NOT_RUN']+counts['READY_LOCAL']
        assert n==p+f+b+u
        return {'sample_freeze_sha256':self.fingerprint,'group':group,'N':n,'P':p,'F':f,'B':b,'U':u,'counts':counts,
                'demonstrated_ratio':p/n if n else None,'engine_coverage':(p+f)/n if n else None,
                'conditional_engine_pass_rate':p/(p+f) if p+f else None,'engine_assessment':'NOT_EXECUTED' if not p+f else 'OBSERVATIONS_RECORDED',
                'events':len(events),'latest_chain_sha256':events[-1]['sha256'] if events else None,'samples':rows,
                'limits':['Not-run/blocked are not demonstrated passes and are not all proved incompatible.',
                          'Recorded attestations and file hashes do not automatically establish real engine execution.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['acceptance','record','summary','freeze-evaluation'])
    parser.add_argument('round_root');parser.add_argument('--sample');parser.add_argument('--input');parser.add_argument('--group',default='evaluation',choices=['development','evaluation'])
    parser.add_argument('--core-version');parser.add_argument('--tool-version');parser.add_argument('--distribution');parser.add_argument('--validation-report')
    args=parser.parse_args();ledger=Ledger(args.round_root)
    if args.command=='summary':result=ledger.summary(args.group)
    elif args.command=='freeze-evaluation':
        if not all((args.core_version,args.tool_version,args.distribution,args.validation_report)):parser.error('Freeze needs versions, distribution and validation report')
        result=ledger.freeze_evaluation(args.core_version,args.tool_version,args.distribution,args.validation_report)
    else:
        if not args.sample or not args.input:parser.error('--sample and --input required')
        data=json.loads(Path(args.input).read_bytes());result=ledger.acceptance(args.sample,data) if args.command=='acceptance' else ledger.result(args.sample,data)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
