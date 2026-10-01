"""Private process fixture: holds the same worker lock without loading AI."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.worker import run_once

library,runtime,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]

def execute(jobs,job,*args):
    if mode=='interrupt':
        jobs.update(job['id'],checkpoint={'import_hash':'durable'})
        (runtime/'claimed').write_text(job['id'],encoding='utf-8')
        time.sleep(30)
    else:
        assert job['checkpoint']=={'import_hash':'durable'}
        assert job['attempts']==2
        jobs.update(job['id'],status='completed',phase='completed')
    return True

raise SystemExit(run_once(library,runtime,execute=execute))
