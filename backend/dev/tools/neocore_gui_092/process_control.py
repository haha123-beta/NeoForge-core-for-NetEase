"""Owned worker tree. Windows job assigned before the suspended worker runs."""
import ctypes,os,signal,subprocess,time

class Cancelled(RuntimeError):pass
class TimedOut(RuntimeError):pass

class OwnedProcess:
    def __init__(self,args,log,env=None):
        self.job=None;self.process=None
        if os.name=='nt':
            from ctypes import wintypes as w
            k=ctypes.WinDLL('kernel32',use_last_error=True);self.kernel=k
            k.CreateJobObjectW.restype=w.HANDLE;k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR]
            k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];k.CloseHandle.argtypes=[w.HANDLE]
            self.job=k.CreateJobObjectW(None,None)
            if not self.job:raise ctypes.WinError(ctypes.get_last_error())
            try:
                class Basic(ctypes.Structure):
                    _fields_=[('ProcessUserTimeLimit',ctypes.c_longlong),('JobUserTimeLimit',ctypes.c_longlong),('LimitFlags',w.DWORD),
                        ('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',w.DWORD),
                        ('Affinity',ctypes.c_size_t),('PriorityClass',w.DWORD),('SchedulingClass',w.DWORD)]
                class IO(ctypes.Structure):_fields_=[('values',ctypes.c_ulonglong*6)]
                class Extended(ctypes.Structure):
                    _fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),
                        ('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
                self.extended_type=Extended
                limits=Extended();limits.BasicLimitInformation.LimitFlags=0x2000 # KILL_ON_JOB_CLOSE
                k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
                if not k.SetInformationJobObject(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)):raise ctypes.WinError(ctypes.get_last_error())
                self.process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=0x4|getattr(subprocess,'CREATE_NO_WINDOW',0))
                if not k.AssignProcessToJobObject(self.job,w.HANDLE(int(self.process._handle))):raise ctypes.WinError(ctypes.get_last_error())
                n=ctypes.WinDLL('ntdll');n.NtResumeProcess.argtypes=[w.HANDLE];n.NtResumeProcess.restype=ctypes.c_long
                status=n.NtResumeProcess(w.HANDLE(int(self.process._handle)))
                if status<0:raise OSError('Cannot resume owned process: '+str(status))
            except BaseException:
                self.close();raise
        else:self.process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)

    def wait(self,timeout,cancel=lambda:False,tick=lambda:None):
        start=time.monotonic()
        try:
            while self.process.poll() is None:
                if cancel():raise Cancelled('用户取消')
                if time.monotonic()-start>=timeout:raise TimedOut('任务达到 '+str(timeout)+' 秒限制；证据已保留')
                tick();time.sleep(.1)
            return self.process.returncode
        finally:self.close()

    def resource_snapshot(self):
        if not self.job:return {'tree_metrics':'UNAVAILABLE'}
        from ctypes import wintypes as w
        value=self.extended_type()
        self.kernel.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p]
        if not self.kernel.QueryInformationJobObject(self.job,9,ctypes.byref(value),ctypes.sizeof(value),None):return {'tree_metrics':'UNKNOWN'}
        class Accounting(ctypes.Structure):
            _fields_=[(n,ctypes.c_longlong) for n in ('TotalUserTime','TotalKernelTime','PeriodUserTime','PeriodKernelTime')]+[(n,w.DWORD) for n in ('PageFaultCount','TotalProcesses','ActiveProcesses','TerminatedProcesses')]
        class BasicIO(ctypes.Structure):
            _fields_=[('basic',Accounting),('io',ctypes.c_ulonglong*6)]
        accounting=BasicIO();ok=self.kernel.QueryInformationJobObject(self.job,8,ctypes.byref(accounting),ctypes.sizeof(accounting),None)
        return dict(tree_metrics='WINDOWS_JOB',peak_job_committed_bytes=value.PeakJobMemoryUsed,
            peak_single_process_committed_bytes=value.PeakProcessMemoryUsed,
            cpu_tree_seconds=(accounting.basic.TotalUserTime+accounting.basic.TotalKernelTime)/10000000.0 if ok else None,
            io_read_bytes=accounting.io[3] if ok else None,io_write_bytes=accounting.io[4] if ok else None,
            processes_total=accounting.basic.TotalProcesses if ok else None,monotonic_seconds=time.monotonic())

    def close(self):
        if self.job:
            from ctypes import wintypes as w
            self.kernel.TerminateJobObject.argtypes=[w.HANDLE,w.UINT]
            self.kernel.TerminateJobObject(self.job,1)
            class Accounting(ctypes.Structure):
                _fields_=[(n,ctypes.c_longlong) for n in ('TotalUserTime','TotalKernelTime','PeriodUserTime','PeriodKernelTime')]+[(n,w.DWORD) for n in ('PageFaultCount','TotalProcesses','ActiveProcesses','TerminatedProcesses')]
            self.kernel.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p]
            deadline=time.monotonic()+10
            while True:
                value=Accounting()
                if not self.kernel.QueryInformationJobObject(self.job,1,ctypes.byref(value),ctypes.sizeof(value),None):break
                if not value.ActiveProcesses or time.monotonic()>=deadline:break
                time.sleep(.01)
            self.kernel.CloseHandle(self.job);self.job=None
        elif self.process and os.name!='nt':
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if self.process and self.process.poll() is None:
            self.process.kill();self.process.wait(timeout=10)
