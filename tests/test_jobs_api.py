"""Durability, recovery, local contract and immutable playback failure tests."""
import contextlib
import asyncio
import io
import json
import os
import tempfile
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from pipeline.api.app import create_app
from pipeline.api.chapters import playback_info
from pipeline.db import Jobs, JobConflict
from pipeline.ingest.hashes import object_hash
from pipeline.store import ChapterStore, write_json
from pipeline.worker import execute_job, run_once
from pipeline.runtime.scheduler import _single_heavy_model


class LocalClient:
    """Use HTTPX's documented ASGI transport without deprecated Starlette glue.

    These fixtures disable the worker; the live golden test covers server lifespan.
    """
    def __init__(self, app):self.app=app
    def request(self, method, url, **kwargs):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='http://testserver') as client:
                return await client.request(method,url,**kwargs)
        return asyncio.run(send())
    def get(self,url,**kwargs):return self.request('GET',url,**kwargs)
    def post(self,url,**kwargs):return self.request('POST',url,**kwargs)
    def close(self):pass


class JobFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TEMP'])
        self.root = Path(self.temp.name)
        self.library = self.root/'library'
        self.runtime = self.root/'runtime'; self.runtime.mkdir()
        self.jobs = Jobs(self.library/'jobs.sqlite3')
        self.source = self.root/'incoming'; self.source.mkdir()
        self.request = {'source':str(self.source),'series':'s','chapter':'c',
                        'settings':{'direction':'rtl','source_language':'en','target_language':'en','pdf_dpi':144}}
        self.client = LocalClient(create_app(self.library,self.runtime,worker=False))

    def tearDown(self):
        self.client.close();self.temp.cleanup()

    def enqueue(self): return self.jobs.enqueue(self.request)


class JobTests(JobFixture):
    def test_duplicate_atomic_and_conflicting_request(self):
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _:self.enqueue(),range(16)))
        self.assertEqual(len({job['id'] for job in results}),1)
        with self.assertRaises(JobConflict):self.jobs.enqueue({**self.request,'source':str(self.root)})
        with self.assertRaises(JobConflict):self.jobs.enqueue({**self.request,'series':'S','chapter':'C'})

    def test_job_survives_database_reopen(self):
        job = self.enqueue()
        self.assertEqual(Jobs(self.jobs.path).get(job['id'])['status'],'queued')
        self.assertEqual(self.client.get('/api/jobs/'+job['id']).json()['request'],self.request)

    def test_interrupted_job_resumes_once_then_requires_retry(self):
        self.enqueue(); first=self.jobs.recover_and_claim()
        self.jobs.update(first['id'],checkpoint={'import_hash':'finished'})
        second=self.jobs.recover_and_claim()
        self.assertEqual(second['id'],first['id']);self.assertEqual(second['attempts'],2)
        self.assertEqual(second['checkpoint'],{'import_hash':'finished'})
        self.assertIsNone(self.jobs.recover_and_claim())
        self.assertEqual(self.jobs.get(first['id'])['status'],'failed')
        self.assertEqual(self.client.post('/api/jobs/'+first['id']+'/retry').status_code,202)

    def test_live_worker_lock_prevents_recovery_or_execution(self):
        self.enqueue();running=self.jobs.recover_and_claim()
        with _single_heavy_model(self.runtime/'job-worker.lock'):
            self.assertEqual(run_once(self.library,self.runtime,execute=lambda *_:self.fail('Worker overlapped')),75)
        self.assertEqual(self.jobs.get(running['id'])['attempts'],1)

    def test_killed_worker_process_releases_lock_and_resumes_checkpoint(self):
        job=self.enqueue()
        probe=Path(__file__).with_name('job_process_probe.py')
        with subprocess.Popen([sys.executable,str(probe),str(self.library),str(self.runtime),'interrupt'],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
            deadline=time.monotonic()+10
            while not (self.runtime/'claimed').exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(.05)
            self.assertTrue((self.runtime/'claimed').exists())
            child.terminate();child.wait(timeout=5)
        completed=subprocess.run([sys.executable,str(probe),str(self.library),str(self.runtime),'resume'],
                                 capture_output=True,text=True,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(self.jobs.get(job['id'])['status'],'completed')

    def test_failure_checkpoint_retry_skips_source_import(self):
        self.enqueue();job=self.jobs.recover_and_claim();store=ChapterStore(self.library,'s','c')
        manifest={'pages':[{'id':'p1'}]};calls=[]
        def importer(*args,**kw):
            calls.append('import');write_json(store.asset('import.json'),manifest);return manifest,{'pages_total':1}
        def fail(*args,**kw):raise RuntimeError('named OCR failure')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(execute_job(self.jobs,job,self.library,self.runtime,importer=importer,analyzer=fail,
                                        compiler=lambda *a,**k:({},{}),publisher=lambda s:{}))
        failed=self.jobs.get(job['id']);self.assertIn('named OCR failure',failed['error'])
        self.assertEqual(failed['checkpoint']['import_hash'],object_hash(manifest))
        self.jobs.retry(job['id']);retry=self.jobs.recover_and_claim()
        self.assertTrue(execute_job(self.jobs,retry,self.library,self.runtime,importer=lambda *a,**k:self.fail('import repeated'),
                                   analyzer=lambda *a,**k:({},{}),compiler=lambda *a,**k:({},{}),publisher=lambda s:{}))
        self.assertEqual(calls,['import']);self.assertEqual(self.jobs.get(job['id'])['status'],'completed')

    def test_changed_checkpoint_manifest_reimports(self):
        self.enqueue();job=self.jobs.recover_and_claim()
        self.jobs.update(job['id'],checkpoint={'import_hash':'stale'})
        job=self.jobs.get(job['id']);calls=[]
        self.assertTrue(execute_job(self.jobs,job,self.library,self.runtime,importer=lambda *a,**k:(calls.append(1) or {},{}),
                                   analyzer=lambda *a,**k:({},{}),compiler=lambda *a,**k:({},{}),publisher=lambda s:{}))
        self.assertEqual(calls,[1])

    def test_retry_only_failed_and_no_parallel_chapter_job(self):
        job=self.enqueue();self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/retry').status_code,409)
        self.jobs.update(job['id'],status='failed');self.enqueue()
        self.assertEqual(self.client.post('/api/jobs/'+job['id']+'/retry').status_code,409)
        self.assertEqual(self.client.get('/api/jobs/missing').status_code,404)

    def test_import_contract_path_extra_origin_and_host(self):
        data={'source':str(self.source),'series':'s','chapter':'c','direction':'rtl'}
        response=self.client.post('/api/imports',json=data)
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(self.client.post('/api/imports',json=data).json()['id'],response.json()['id'])
        for extra in ({'source':'C:\\Windows'},{'series':'../escape'},{'direction':'up'},{'secret':'x'},{'source':str(self.root)}):
            self.assertEqual(self.client.post('/api/imports',json={**data,**extra}).status_code,422)
        self.assertEqual(self.client.post('/api/imports',json=data,headers={'Origin':'https://foreign.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/health',headers={'Host':'foreign.example'}).status_code,400)
        self.assertEqual(self.client.get('/api/unknown').status_code,404)
        self.assertEqual(self.client.get('/.env').status_code,404)

    def test_unknown_playback_visible_and_no_source_routes(self):
        self.assertEqual(self.client.get('/api/chapters/s/c/playback').status_code,409)
        self.assertEqual(self.client.get('/api/chapters/s/c/sources/file').status_code,404)

    def test_existing_windows_case_alias_rejected_before_enqueue(self):
        (self.library/'Existing').mkdir()
        data={'source':str(self.source),'series':'existing','chapter':'chapter'}
        self.assertEqual(self.client.post('/api/imports',json=data).status_code,422)

    def test_api_failed_job_visible_in_library(self):
        job=self.enqueue();self.jobs.update(job['id'],status='failed',error='Missing page 3')
        card=self.client.get('/api/library').json()['chapters'][0]
        self.assertEqual(card['job']['error'],'Missing page 3');self.assertFalse(card['playable'])


class PlaybackTests(JobFixture):
    def setUp(self):
        super().setUp()
        self.store=ChapterStore(self.library,'s','c')
        self.image=self.store.asset('pages/page.jpg');self.image.parent.mkdir(parents=True);self.image.write_bytes(b'original pixels')
        # Structural contract validation is tested with real MotionScript in golden integration;
        # this minimal fixture isolates serving and snapshot behavior without repeating it.
        self.script={'version':1,'chapter':'s/c','direction':'rtl','pages':[{'image':'pages/page.jpg','panels':[]}], 'characters':{}}
        write_json(self.store.asset('motionscript.json'),self.script)
        with patch('pipeline.api.chapters.validate_contract'):
            self.info=playback_info(self.store)

    def test_old_snapshot_survives_new_script_and_only_serves_declared_assets(self):
        self.assertEqual(self.client.get(self.info['script_url']).json(),self.script)
        self.assertEqual(self.client.get(self.info['asset_base']+'pages/page.jpg').content,b'original pixels')
        self.assertEqual(self.client.get(self.info['asset_base']+'sources/page.jpg').status_code,404)
        write_json(self.store.asset('motionscript.json'),{**self.script,'direction':'ltr'})
        self.assertEqual(self.client.get(self.info['script_url']).json()['direction'],'rtl')

    def test_mutated_art_is_not_served(self):
        self.image.write_bytes(b'changed pixels')
        self.assertEqual(self.client.get(self.info['asset_base']+'pages/page.jpg').status_code,409)

    def test_corrupt_snapshot_is_rejected_and_reopening_repairs_it(self):
        path=self.store.asset('cache/playback/'+self.info['snapshot']+'.json')
        record=json.loads(path.read_text(encoding='utf-8'));record['assets']['pages/page.jpg']='incorrect';write_json(path,record)
        self.assertEqual(self.client.get(self.info['script_url']).status_code,409)
        with patch('pipeline.api.chapters.validate_contract'):playback_info(self.store)
        self.assertEqual(self.client.get(self.info['script_url']).status_code,200)


if __name__ == '__main__':unittest.main()
