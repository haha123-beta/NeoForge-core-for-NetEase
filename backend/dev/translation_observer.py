"""Opt-in developer evidence, never installed in the production Python2 runtime."""
import contextlib,json,os,time,traceback
from pathlib import Path

def metrics():
    result={'cpu_seconds':time.process_time(),'memory_peak_bytes':None,'memory_current_bytes':None,'io_read_bytes':None,'io_write_bytes':None}
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes as w
        class Memory(ctypes.Structure):
            _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        class IO(ctypes.Structure):
            _fields_=[(n,ctypes.c_ulonglong) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=w.HANDLE
        handle=kernel.GetCurrentProcess();m=Memory();m.cb=ctypes.sizeof(m);io=IO()
        ps=ctypes.WinDLL('psapi',use_last_error=True);ps.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Memory),w.DWORD]
        kernel.GetProcessIoCounters.argtypes=[w.HANDLE,ctypes.POINTER(IO)]
        if ps.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):result.update(memory_peak_bytes=m.PeakWorkingSetSize,memory_current_bytes=m.WorkingSetSize)
        if kernel.GetProcessIoCounters(handle,ctypes.byref(io)):result.update(io_read_bytes=io.ReadTransferCount,io_write_bytes=io.WriteTransferCount)
    return result

def event(phase,state,**values):
    target=os.environ.get('NEOCORE_OBSERVABILITY_DIR')
    if not target:return
    root=Path(target);root.mkdir(parents=True,exist_ok=True)
    value=dict(phase=phase,state=state,monotonic_seconds=time.monotonic(),pid=os.getpid(),metrics=metrics(),**values)
    with (root/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(value,ensure_ascii=False)+'\n')
    temp=root/'live.tmp';temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
    # Windows readers and antivirus may briefly deny destination replacement.
    # The append-only journal already owns this evidence; a stale preview must
    # not turn a successful compiler step into a semantic conversion failure.
    for attempt in range(10):
        try:temp.replace(root/'live.json');break
        except PermissionError as error:
            if attempt<9:time.sleep(.005);continue
            warning=dict(phase='observability_live',state='STALE_SNAPSHOT',
                monotonic_seconds=time.monotonic(),pid=os.getpid(),error_type=type(error).__name__,
                error=str(error),journal_event_preserved=True,retry_attempts=10)
            with (root/'events.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(warning,ensure_ascii=False)+'\n')
            try:temp.unlink()
            except OSError:pass

@contextlib.contextmanager
def span(phase,**values):
    start=time.perf_counter();event(phase,'STARTED',**values)
    try:yield
    except BaseException as error:
        event(phase,'ERROR',elapsed_seconds=time.perf_counter()-start,error_type=type(error).__name__,error=str(error),**values)
        raise
    else:event(phase,'FINISHED',elapsed_seconds=time.perf_counter()-start,**values)

def call(phase,function,*args,observation=None,**kwargs):
    with span(phase,**(observation or {})):return function(*args,**kwargs)
