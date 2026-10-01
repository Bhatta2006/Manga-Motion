"""Pinned Qwen vision through an isolated, stage-owned llama.cpp process."""
from __future__ import annotations
import base64
import ctypes
import io
import json
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path
import httpx
from PIL import Image
from pipeline.cache import page_sha256
from pipeline.director.prompt import prompt, REVISION as PROMPT_REVISION
from pipeline.director.validate import output_schema, decode_output
from pipeline.adapters.director_base import fallback
from pipeline.ingest.hashes import object_hash
from pipeline.runtime.process_tree import ChildJob

PROJECT=Path(__file__).resolve().parents[2]
SPEC=json.loads((PROJECT/'pipeline/director/local-runtime.json').read_text())


def child_peak_ram(pid):
    if os.name!='nt':return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD),
                  *[(k,ctypes.c_size_t) for k in ('peak','working','qpp','qp','qnp','qn','pf','ppf')]]
    kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000|0x0010,False,pid)
    if not handle:return None
    try:
        value=Counters();value.cb=ctypes.sizeof(value)
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        return round(value.peak/2**20) if ctypes.windll.psapi.GetProcessMemoryInfo(handle,ctypes.byref(value),value.cb) else None
    finally:kernel.CloseHandle(handle)


class LocalQwenDirector:
    stage_name='local-director'
    revision=f'qwen3-vl-2b-q8-{SPEC["revision"][:12]}-b11323-{PROMPT_REVISION}'
    heavy=True
    def __init__(self,records,contexts=None,*,spec=None):
        self.records,self.contexts=records,contexts or {}
        self.spec=spec or SPEC
        self.revision=f'{self.spec["model_id"].split("/")[-1]}-{self.spec["weights"][0]["sha256"][:12]}-b11323-{PROMPT_REVISION}'
        self.process=None;self.client=None;self.log=None;self.child_job=None
        self.stats={'requests':0,'invalid_outputs':0,'subprocess_ram_peak_mib':None,'tokens':0}
        self.last_failures=[]

    def load(self):
        binary=(PROJECT/self.spec['runtime_root']/'llama-server.exe').resolve()
        model_root=(PROJECT/self.spec['model_root']).resolve()
        if binary.drive.upper()!='D:' or model_root.drive.upper()!='D:':raise ValueError('Director runtime/model must be on D:')
        if not binary.is_file():raise ValueError('Install the verified local director with scripts/install-director.ps1')
        for weight in self.spec['weights']:
            path=model_root/weight['file']
            if not path.is_file() or path.stat().st_size!=weight['bytes'] or page_sha256(path)!=weight['sha256']:
                raise ValueError('Director weight is missing or has a checksum mismatch')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        logs=PROJECT/'.runtime/director-logs';logs.mkdir(parents=True,exist_ok=True)
        self.log=(logs/f'{uuid.uuid4().hex}.log').open('wb')
        args=[str(binary),'-m',str(model_root/self.spec['weights'][0]['file']),
              '--mmproj',str(model_root/self.spec['weights'][1]['file']),
              '--host','127.0.0.1','--port',str(port),'--no-webui',
              '--ctx-size',str(self.spec['context_tokens']),'--parallel','1','--threads',str(self.spec['cpu_threads']),
              '--gpu-layers','all','--flash-attn','on','--image-max-tokens',str(self.spec['image_max_tokens']),
              '--mtmd-batch-max-tokens','256','--alias','mangamotion-director']
        self.process=subprocess.Popen(args,cwd=binary.parent,stdout=self.log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.child_job=ChildJob(self.process.pid)
        self.client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=180,trust_env=False)
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if self.process.poll() is not None:raise RuntimeError('Local director exited during startup; inspect private runtime log')
            try:
                if self.client.get('/health',timeout=1).is_success:return
            except httpx.HTTPError:pass
            time.sleep(.1)
        raise TimeoutError('Local director startup timed out')

    def unload(self):
        if self.process:
            if self.process.poll() is None:
                self.stats['subprocess_ram_peak_mib']=child_peak_ram(self.process.pid)
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
            self.process=None
        if self.child_job:self.child_job.close();self.child_job=None
        if self.client:self.client.close();self.client=None
        if self.log:self.log.close();self.log=None

    def run_page(self,page):
        digest=page_sha256(page);record=self.records[digest]
        content=[{'type':'text','text':prompt(record,self.contexts.get(digest,''))}]
        with Image.open(page) as image:
            # Analysis-only crops; original bytes and serving textures stay intact.
            images=[image.copy()]+[image.crop(tuple(round(x) for x in p['bbox'])) for p in record['panels']]
            for index,crop in enumerate(images):
                label='Full manga page' if index==0 else 'Panel crop: '+record['panels'][index-1]['id']
                content.append({'type':'text','text':label})
                buffer=io.BytesIO();crop.convert('RGB').save(buffer,format='PNG')
                content.append({'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()}})
                crop.close()
        request={'model':'mangamotion-director','messages':[{'role':'user','content':content}],
                 'temperature':0,'seed':4050,'max_tokens':3500,
                 'response_format':{'type':'json_schema','json_schema':{'name':'manga_scene','schema':output_schema(record)}},
                 'chat_template_kwargs':{'enable_thinking':False}}
        reason='semantic_output_unresolved'
        for attempt in range(2):
            self.stats['requests']+=1
            try:
                response=self.client.post('/v1/chat/completions',json=request)
                response.raise_for_status();data=response.json()
                self.stats['tokens']+=data.get('usage',{}).get('total_tokens',0)
                if data['choices'][0].get('finish_reason')=='length':raise ValueError('Semantic output exceeded token budget')
                output=decode_output(json.loads(data['choices'][0]['message']['content']),record)
                return {**output,'semantic_sha256':object_hash(output),'provider':'local-qwen3-vl','needs_review':True,
                        'review_reasons':['semantic_accuracy_unverified'],'attempts':attempt+1}
            except (httpx.HTTPError,ValueError,KeyError,TypeError,IndexError) as exc:
                self.stats['invalid_outputs']+=1
                self.last_failures.append({'error_type':type(exc).__name__,'validation':str(exc)[:200] if isinstance(exc,ValueError) else 'transport or response failure'})
                request['messages'][0]['content'][0]['text'] += '\nCorrection: output must include every panel and every assigned text exactly once, with the exact input IDs.'
                # Do not log prompt/image/response or include transport body in errors.
                reason='semantic_response_invalid_or_unavailable'
        result={**fallback(record,reason),'attempts':2}
        return {**result,'semantic_sha256':object_hash({k:result[k] for k in ('summary','panels')})}

    def report_metrics(self):return dict(self.stats)
