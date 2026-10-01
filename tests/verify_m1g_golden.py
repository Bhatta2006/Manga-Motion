"""Real local job: all model caches reused, first prefix observed before completion."""
import json
import os
import shutil
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.store import write_json
from pipeline.cache import page_sha256
root=Path(__file__).resolve().parents[1]
target=root/'library/golden-m1g/chapter'
target.mkdir(parents=True,exist_ok=True)
shutil.copytree(root/'library/golden-m1d/chapter/cache/stages',target/'cache/stages',dirs_exist_ok=True)
base=os.environ.get('MANGAMOTION_API','http://127.0.0.1:5174')
started=time.perf_counter();first=None;seen=[]
with httpx.Client(base_url=base,timeout=30) as client:
    response=client.post('/api/imports',json={'source':str(root/'library/fixtures/m1a/golden.cbz'),
                                           'series':'golden-m1g','chapter':'chapter','direction':'rtl'})
    response.raise_for_status();job=response.json()
    while time.perf_counter()-started<120:
        status=client.get('/api/jobs/'+job['id']).json()
        if status['status']=='failed':raise AssertionError(status['error'])
        info=client.get('/api/chapters/golden-m1g/chapter/playback')
        if info.is_success:
            info=info.json();seen.append({'seconds':round(time.perf_counter()-started,6),'pages':info['pages'],'status':status['status']})
            if first is None:first=seen[-1]
        if status['status']=='completed':break
        time.sleep(.03)
    else:raise AssertionError('job timed out')
elapsed=time.perf_counter()-started
assert first and first['status']=='running' and first['pages']<5, first
metrics=status['metrics']
assert all(s['cache_hits']==5 for s in metrics['analysis']['stages']), metrics['analysis']['stages']
manifest=json.loads((target/'import.json').read_text())
assert all(page_sha256(target/p['image'])==p['page_sha256'] for p in manifest['pages'])
result={'first_observed':first,'observations':seen,'request_seconds':round(elapsed,6),'metrics':metrics,'source_hashes_unchanged':True}
write_json(root/'reports/M1g-golden.json',result)
print(json.dumps({'first_observed':first,'request_seconds':result['request_seconds'],
                  'worker_seconds':metrics['worker_seconds'],'first_worker_readable_seconds':metrics['first_readable_seconds'],
                  'streaming':metrics['streaming'],'analysis_cache_hits':[s['cache_hits'] for s in metrics['analysis']['stages']],
                  'camera':{'seconds':metrics['camera']['elapsed_seconds'],'hits':metrics['camera']['stage']['cache_hits']},
                  'source_hashes_unchanged':True},indent=2))
