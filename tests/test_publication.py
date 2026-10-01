import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.store import write_json,read_json
from pipeline.runtime.process_tree import ChildJob


class PublicationTests(unittest.TestCase):
    def test_transient_windows_replace_and_persistent_failure_preserve_artifact(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            path=Path(tmp)/'record.json';write_json(path,{'value':'old'})
            error=PermissionError('sharing violation');error.winerror=32
            with patch('pipeline.store.os.replace',side_effect=[error,error,None]) as mocked,patch('pipeline.store.time.sleep'):
                write_json(path,{'value':'new'})
                self.assertEqual(mocked.call_count,3)
            # Mocked final replace did not mutate disk; test actual preservation.
            with patch('pipeline.store.os.replace',side_effect=error),patch('pipeline.store.time.sleep'):
                with self.assertRaises(PermissionError):write_json(path,{'value':'bad'})
            self.assertEqual(read_json(path),{'value':'old'})
            self.assertEqual(list(Path(tmp).glob('*.tmp')),[])

    def test_concurrent_readers_never_see_partial_json(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            path=Path(tmp)/'record.json';write_json(path,{'value':0,'data':'a'*12000})
            stop=threading.Event();failures=[]
            def reader():
                while not stop.is_set():
                    value=read_json(path)
                    if value is None or value.get('data')!='a'*12000:failures.append(value)
            thread=threading.Thread(target=reader);thread.start()
            try:
                for i in range(100):write_json(path,{'value':i,'data':'a'*12000})
            finally:stop.set();thread.join()
            self.assertEqual(failures,[])

    @unittest.skipUnless(os.name=='nt','Windows subprocess ownership')
    def test_owner_exit_kills_owned_subprocess(self):
        code="from pipeline.runtime.process_tree import ChildJob; import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)']); j=ChildJob(p.pid); print(p.pid,flush=True); time.sleep(90)"
        owner=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        pid=None
        try:
            pid=int(owner.stdout.readline());owner.terminate();owner.wait(timeout=5)
            import ctypes
            from ctypes import wintypes
            k=ctypes.WinDLL('kernel32',use_last_error=True)
            k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
            k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.WaitForSingleObject.restype=wintypes.DWORD
            k.CloseHandle.argtypes=[wintypes.HANDLE]
            handle=k.OpenProcess(0x100000,False,pid)
            if handle:
                try:self.assertEqual(k.WaitForSingleObject(handle,5000),0)
                finally:k.CloseHandle(handle)
        finally:
            if owner.poll() is None:owner.terminate();owner.wait(timeout=5)
            owner.stdout.close();owner.stderr.close()
