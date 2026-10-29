"""Per-translation disk cache of immutable parser results, never codegen results.

Lifetime/context isolation prevents reuse across versions, jobs or dependency
profiles. JSON reload returns fresh objects for each compiler phase.
"""
import hashlib,json,tempfile,os
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()

class ParseCache:
    def __init__(self,context,enabled=True,max_entry_bytes=32*1024*1024,max_total_bytes=512*1024*1024):
        self.context_sha=sha(json.dumps(context,sort_keys=True,separators=(',',':')).encode())
        self.enabled=enabled;self.max_entry_bytes=max_entry_bytes;self.max_total_bytes=max_total_bytes;self.total_bytes=0;self.entries={};self.directory=None
    def __enter__(self):
        if self.enabled:
            parent=os.environ.get('NEOCORE_OBSERVABILITY_DIR')
            if parent:Path(parent).mkdir(parents=True,exist_ok=True)
            self.directory=tempfile.TemporaryDirectory(prefix='.parser_ir_cache_',dir=parent)
        return self
    def __exit__(self,*args):
        if self.directory:self.directory.cleanup()
    def parse(self,source,origin,known,parser,notify=lambda **values:None):
        if not self.enabled:return parser(source,origin,known)
        key=sha(json.dumps(dict(source_sha256=sha(source),origin=origin,known=sorted(known),context=self.context_sha),sort_keys=True,separators=(',',':')).encode())
        entry=self.entries.get(key)
        if entry:
            path,digest=entry;raw=path.read_bytes()
            if sha(raw)!=digest:raise ValueError('Parser cache integrity mismatch: '+origin)
            ir=json.loads(raw)
            if ir['origin']!=origin or ir['source_sha256']!=sha(source):raise ValueError('Parser cache source identity mismatch: '+origin)
            notify(state='HIT',file=origin,context_sha256=self.context_sha)
            return ir
        ir=parser(source,origin,known);raw=json.dumps(ir,ensure_ascii=True,separators=(',',':')).encode()
        if len(raw)<=self.max_entry_bytes and self.total_bytes+len(raw)<=self.max_total_bytes:
            path=Path(self.directory.name)/(key+'.json');path.write_bytes(raw);self.entries[key]=(path,sha(raw))
            self.total_bytes+=len(raw)
            notify(state='STORED',file=origin,bytes=len(raw),context_sha256=self.context_sha)
        else:notify(state='NOT_CACHED_OVERSIZE',file=origin,bytes=len(raw),context_sha256=self.context_sha)
        return ir
