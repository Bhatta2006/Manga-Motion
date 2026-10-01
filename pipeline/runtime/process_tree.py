"""Windows model child ownership; closing the owner kills its subprocess tree.

Win32 Job API fields/constants verified against Microsoft Learn, 2026-10-02.
"""
import ctypes
import os


class ChildJob:
    def __init__(self, pid):
        self.handle=None
        if os.name!='nt':return
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),
                      ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('active',w.DWORD),
                      ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),*[(name,ctypes.c_size_t) for name in ('process_memory','job_memory','peak_process','peak_job')]]
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        k=self.kernel
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];k.CreateJobObjectW.restype=w.HANDLE
        k.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];k.SetInformationJobObject.restype=w.BOOL
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
        k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];k.AssignProcessToJobObject.restype=w.BOOL
        k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        process=None
        try:
            limits=Extended();limits.basic.flags=0x2000 # KILL_ON_JOB_CLOSE
            if not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):raise ctypes.WinError(ctypes.get_last_error())
            process=k.OpenProcess(0x0100|0x0001,False,pid) # SET_QUOTA | TERMINATE
            if not process or not k.AssignProcessToJobObject(self.handle,process):raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.close();raise
        finally:
            if process:k.CloseHandle(process)

    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
