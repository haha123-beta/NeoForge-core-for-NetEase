"""Allowlisted task evidence only; no arbitrary paths or request/config secrets."""
import hashlib,json,zipfile,re
from pathlib import Path
from diagnostic_contract import summarize

ALLOWED={'worker.log','worker_failure.log','failure.log','decompile.log','result.json','progress.json',
         'events.jsonl','live.json','partial_translation.json','translation_report.json','manual_review.txt',
         'failures.log','job_report.json','dependency_abi.json','content_manifest.json','performance.json','worker_resources.jsonl','task_identity.json','decompiler_recovery.json'}
ALLOWED.update({'receipt.json','execution.log','item_content_report.json'})
ALLOWED.update({'data_report.json','data_ir_report.html'})
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def redact_text(text):
    return re.sub(r'(?i)((?:api[_-]?key|access[_-]?token|token|authorization|password|secret)\s*[:=]\s*)[^\s,;]+',r'\1[REDACTED]',text)

def scrub(value):
    if isinstance(value,dict):return {k:('[REDACTED]' if re.fullmatch(r'(?i)(?:api[_-]?key|access[_-]?token|token|authorization|password|secret)',k) else scrub(v)) for k,v in value.items()}
    if isinstance(value,list):return [scrub(v) for v in value]
    if isinstance(value,str):return redact_text(value)
    return value

def snapshot(folder,job):
    folder=Path(folder)
    if folder.is_symlink() or (hasattr(folder,'is_junction') and folder.is_junction()):raise ValueError('诊断根目录不允许链接')
    folder=folder.resolve()
    if folder.name!=job.get('attempt'):raise ValueError('诊断目录与任务不匹配')
    evidence={};unreadable=[];raw_hashes={}
    for p in sorted(folder.rglob('*')):
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('诊断路径不允许链接')
        if not p.is_file() or (p.name not in ALLOWED and not re.fullmatch(r'[0-9]+(?:-[0-9]+)?\.parser\.stderr\.log',p.name)):continue
        if p.is_symlink() or not p.resolve().is_relative_to(folder):raise ValueError('诊断路径越界')
        raw=p.read_bytes();name=p.relative_to(folder).as_posix()
        raw_hashes[name]=hashlib.sha256(raw).hexdigest()
        if p.suffix=='.json':
            try:json.loads(raw)
            except (ValueError,UnicodeError):unreadable.append(name);continue
        # Credentials never belong to task diagnostics. Preserve the structure
        # and mark values rather than dropping an entire diagnostic file.
        text=redact_text(raw.decode('utf-8',errors='replace'))
        if p.suffix=='.json':
            # JSON redaction must run on the original object; regex replacement
            # may remove quotes in arbitrary log-style text.
            text=json.dumps(scrub(json.loads(raw)),ensure_ascii=False,indent=2)
        elif p.suffix=='.jsonl':
            redacted=[]
            for line in raw.splitlines():
                try:redacted.append(json.dumps(scrub(json.loads(line)),ensure_ascii=False))
                except (ValueError,UnicodeError):unreadable.append(name+':partial_tail')
            text='\n'.join(redacted)+'\n'
        raw=text.encode('utf-8')
        evidence[name]=raw
    events=[]
    for line in evidence.get('events.jsonl',b'').splitlines():
        try:events.append(json.loads(line))
        except (ValueError,UnicodeError):unreadable.append('events.jsonl:partial_tail')
    phases={};peak=0
    for e in events:
        if 'elapsed_seconds' in e:phases[e['phase']]=phases.get(e['phase'],0)+e['elapsed_seconds']
        peak=max(peak,e.get('metrics',{}).get('memory_peak_bytes') or 0)
    performance=dict(phase_summed_seconds=phases,worker_memory_high_water_bytes=peak or None,
        memory_scope='Worker process cumulative high-water, not independent per-file allocation; child JVM excluded',
        phase_scope='Some codegen includes interleaved linking; sums are not additive wall-clock decomposition',
        events=len(events),status=job['status'])
    resources=[]
    for line in evidence.get('worker_resources.jsonl',b'').splitlines():
        try:resources.append(json.loads(line))
        except ValueError:unreadable.append('worker_resources.jsonl:partial_tail')
    if resources:
        performance['process_tree_samples']=len(resources)
        performance['tree_peak_committed_bytes']=max((r.get('peak_job_committed_bytes') or 0 for r in resources),default=0)
        measured=[r for r in resources if r.get('cpu_tree_seconds') is not None]
        performance['tree_cpu_seconds']=max((r['cpu_tree_seconds'] for r in measured),default=None)
        performance['tree_io_read_bytes']=max((r['io_read_bytes'] for r in measured if r.get('io_read_bytes') is not None),default=None)
        performance['tree_io_write_bytes']=max((r['io_write_bytes'] for r in measured if r.get('io_write_bytes') is not None),default=None)
        performance['tree_metric_scope']='Windows Job object including descendant Python/JVM processes, sampled; committed memory is not working set'
    report=dict(schema_version=1,version='0.9.2',job_id=job['id'],attempt=job['attempt'],
        input_sha256=job['sha256'],status=job['status'],engine_verified=False,
        export_kind='DIAGNOSTIC_EVIDENCE_NOT_EXECUTABLE',performance=performance,
        incomplete_evidence=unreadable,source_reports=[])
    for name,raw in evidence.items():
        if name.endswith('translation_report.json'):report['source_reports'].append(json.loads(raw))
    if not report['source_reports'] and 'partial_translation.json' in evidence:
        report['source_reports']=[json.loads(evidence['partial_translation.json'])];report['translation_is_partial_checkpoint']=True
    if 'result.json' in evidence:report['result']=json.loads(evidence['result.json'])
    report['structured_diagnostics']=summarize(report['source_reports'])
    report['validation_stages']={
        'packaging_status':job.get('artifact_kind') or job.get('status'),
        'python2_executed':report.get('result',{}).get('python2_executed',False),
        'engine_verified':False}
    report['evidence']={n:hashlib.sha256(v).hexdigest() for n,v in evidence.items()}
    report['raw_source_evidence_sha256']=raw_hashes
    report['export_transform']='Credential-redacted snapshot; original logs stay local, original and exported hashes recorded separately'
    report['report_completeness']='PARTIAL_CHECKPOINT' if unreadable or job['status'] in ('RUNNING','QUEUED','TIMED_OUT','CANCELLED','INTERRUPTED') else 'AVAILABLE_EVIDENCE_SNAPSHOT'
    return report,evidence

def archive(folder,job,target):
    report,evidence=snapshot(folder,job);target=Path(target)
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('diagnostic_report.json',json.dumps(report,ensure_ascii=False,indent=2))
        for n,raw in evidence.items():z.writestr('evidence/'+n,raw)
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise ValueError('诊断 ZIP 校验失败')
        actual=json.loads(z.read('diagnostic_report.json'))
        if (actual['job_id'],actual['attempt'],actual['input_sha256'])!=(job['id'],job['attempt'],job['sha256']):raise ValueError('诊断归属校验失败')
        for n,h in report['evidence'].items():
            if hashlib.sha256(z.read('evidence/'+n)).hexdigest()!=h:raise ValueError('诊断证据校验失败')
    return report
