"""Local optimistic correction saves; CPU rebuild and crash-safe paired publication."""
import time
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from starlette.responses import Response
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.ingest.hashes import object_hash
from pipeline.cache import page_sha256
from pipeline.review.corrections import load,validate,recover,AUDITS
from pipeline.review.issues import review
from pipeline.build_motion import build_motion
from pipeline.api.chapters import playback_info

class CorrectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    expected_revision:str=Field(pattern=r'^[a-f0-9]{64}$')
    corrections:dict

def router(jobs,library,runtime):
    routes=APIRouter()
    def store_for(series,chapter):
        try:return ChapterStore(library,series,chapter)
        except ValueError as exc:raise HTTPException(404,'Unknown chapter') from exc
    def idle():
        if any(j['status'] in ('queued','running') for j in jobs.list()):raise HTTPException(409,'Wait for current processing to finish before saving corrections')
    @routes.get('/api/chapters/{series}/{chapter}/review')
    def listing(series:str,chapter:str):
        store=store_for(series,chapter)
        try:
            with store.lock():recover(store);return review(store)
        except (ValueError,OSError,KeyError,TypeError) as exc:raise HTTPException(409,str(exc)) from exc
    @routes.get('/api/chapters/{series}/{chapter}/review/pages/{digest}')
    def page(series:str,chapter:str,digest:str):
        store=store_for(series,chapter);analysis=read_json(store.asset('analysis.json')) or {}
        source=next((p for p in analysis.get('pages',[]) if p['page_sha256']==digest),None)
        if not source:raise HTTPException(404,'Unknown review page')
        path=store.asset(source['image']);content=path.read_bytes()
        import hashlib,mimetypes
        if hashlib.sha256(content).hexdigest()!=digest:raise HTTPException(409,'Original page changed')
        return Response(content,media_type=mimetypes.guess_type(path.name)[0],headers={'Cache-Control':'no-store'})
    @routes.post('/api/chapters/{series}/{chapter}/review')
    def save(series:str,chapter:str,request:CorrectionRequest):
        idle();store=store_for(series,chapter)
        try:
            with store.lock():
                idle();recover(store);analysis=read_json(store.asset('analysis.json'))
                if not analysis:raise ValueError('No current analysis')
                current=load(store,analysis)
                if object_hash(current)!=request.expected_revision:raise ValueError('Corrections changed in another window; reload review before saving')
                validate(request.corrections,store,analysis)
                for page in analysis['pages']:
                    if page_sha256(store.asset(page['image']))!=page['page_sha256']:raise ValueError('Original page changed')
                journal={'state':'pending','previous_corrections':read_json(store.asset('corrections.json')),'previous_script':read_json(store.asset('motionscript.json')),
                         'previous_audits':{name:read_json(store.asset(name)) for name in AUDITS}}
                write_json(store.asset('cache/review-transaction.json'),journal);started=time.perf_counter()
                try:
                    write_json(store.asset('corrections.json'),request.corrections)
                    _,metrics=build_motion(library,series,chapter,runtime,locked=True)
                    info=playback_info(store);data=review(store)
                    journal['state']='committed';write_json(store.asset('cache/review-transaction.json'),journal)
                except Exception:recover(store);raise
                return {**data,'playback':info,'elapsed_seconds':round(time.perf_counter()-started,6),'metrics':metrics}
        except (ValueError,OSError,KeyError,TypeError) as exc:raise HTTPException(409,str(exc)) from exc
    return routes
