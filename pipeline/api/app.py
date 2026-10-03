"""Loopback Library service. Start with python -m pipeline.api.app."""
from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from pipeline.api.chapters import library_entries, playback_info, read_snapshot, asset_response
from pipeline.api.jobs import router
from pipeline.db import Jobs
from pipeline.store import ChapterStore
from pipeline.build_motion import build_motion
from pipeline.worker import WorkerCoordinator

PROJECT = Path(__file__).resolve().parents[2]


class PacingRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reading_wpm: int = Field(ge=80, le=600)


def create_app(library=PROJECT/'library', runtime=PROJECT/'.runtime', *, worker=True, dist=None):
    library, runtime = Path(library).resolve(), Path(runtime).resolve()
    for path in (library,runtime):
        if path.drive.upper() != 'D:': raise ValueError('Library and runtime must be on D:')
    # Check links before creating writable database/log locations.
    store = ChapterStore(library,'path-check','path-check')
    store.checked(library/'jobs.sqlite3')
    if not runtime.is_dir(): raise ValueError('Enter the D-drive runtime before starting the service')
    jobs = Jobs(library/'jobs.sqlite3')
    coordinator = WorkerCoordinator(library,runtime) if worker else None

    @asynccontextmanager
    async def lifespan(app):
        if coordinator: coordinator.start()
        try: yield
        finally:
            if coordinator: coordinator.close()

    app = FastAPI(title='MangaMotion local Library', version='0.1.0', lifespan=lifespan)
    app.state.jobs, app.state.coordinator = jobs, coordinator
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver'])

    @app.middleware('http')
    async def local_write(request: Request, call_next):
        if request.method in {'POST','PUT','PATCH','DELETE'}:
            origin = request.headers.get('origin')
            expected = f'{request.url.scheme}://{request.headers.get("host", "")}'
            if origin is not None and origin != expected:
                return JSONResponse({'detail':'Import and retry requests must come from this Library'},status_code=403)
        response = await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    app.include_router(router(jobs, library))
    from pipeline.api.review import router as review_router
    from pipeline.review.corrections import recover
    for path in library.glob('*/*/cache/review-transaction.json'):
        with ChapterStore(library,path.parent.parent.parent.name,path.parent.parent.name).lock():
            recover(ChapterStore(library,path.parent.parent.parent.name,path.parent.parent.name))
    app.include_router(review_router(jobs,library,runtime))

    @app.get('/api/health')
    def health():
        return {'status':'ok', 'worker':bool(coordinator), 'worker_error':coordinator.last_error if coordinator else None}

    @app.get('/api/library')
    def listing():
        return {'chapters':library_entries(library,jobs.list()), 'worker_error':coordinator.last_error if coordinator else None}

    def chapter_store(series, chapter):
        try: return ChapterStore(library,series,chapter)
        except ValueError as exc: raise HTTPException(404,'Unknown chapter') from exc

    @app.get('/api/chapters/{series}/{chapter}/playback')
    def playback(series: str, chapter: str):
        try:
            store=chapter_store(series,chapter)
            from pipeline.streaming import streaming_record
            latest=next((j for j in jobs.list() if j['series']==series and j['chapter']==chapter),None)
            stream=streaming_record(store,latest['id']) if latest and latest['status']!='completed' else None
            info=playback_info(store,stream=stream)
            return {**info,'processing_status':latest['status'] if latest else 'completed',
                    'processing_error':latest['error'] if latest else None}
        except (ValueError,OSError,KeyError,TypeError) as exc: raise HTTPException(409,str(exc)) from exc

    @app.post('/api/chapters/{series}/{chapter}/pacing')
    def pacing(series: str, chapter: str, request: PacingRequest):
        if any(j['status'] in ('queued','running') for j in jobs.list()):
            raise HTTPException(409,'Wait for current processing to finish before changing reading speed')
        store = chapter_store(series,chapter)
        try:
            _, metrics = build_motion(library,series,chapter,runtime,reading_wpm=request.reading_wpm,persist_rate=True)
            return {**playback_info(store), 'elapsed_seconds':metrics['elapsed_seconds']}
        except (ValueError,OSError,KeyError,TypeError) as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.get('/api/chapters/{series}/{chapter}/playback/{digest}/motionscript.json')
    def script(series: str, chapter: str, digest: str):
        return read_snapshot(chapter_store(series,chapter),digest)['script']

    @app.get('/api/chapters/{series}/{chapter}/playback/{digest}/manifest')
    def offline_manifest(series: str, chapter: str, digest: str):
        record=read_snapshot(chapter_store(series,chapter),digest)
        return {'snapshot':digest,'assets':record['assets']}

    @app.get('/api/chapters/{series}/{chapter}/playback/{digest}/assets/{kind}/{leaf}')
    def asset(series: str, chapter: str, digest: str, kind: str, leaf: str):
        try: return asset_response(chapter_store(series,chapter),digest,f'{kind}/{leaf}')
        except (ValueError,OSError) as exc: raise HTTPException(409,str(exc)) from exc

    dist = Path(dist) if dist else PROJECT/'reader/dist'
    @app.get('/sw.js')
    def service_worker():
        import hashlib,json
        from starlette.responses import Response
        if not (dist/'index.html').is_file():raise HTTPException(503,'Build reader first')
        files=['/','/manifest.webmanifest','/icon.svg','/icon-192.png','/icon-512.png']+['/assets/'+p.name for p in sorted((dist/'assets').iterdir()) if p.suffix in ('.js','.css')]
        build=hashlib.sha256((dist/'index.html').read_bytes()).hexdigest()[:16]
        source=(dist/'sw.js').read_text(encoding='utf-8').replace('__BUILD_ID__',build).replace('__SHELL_FILES__',json.dumps(files))
        return Response(source,media_type='application/javascript',headers={'Cache-Control':'no-cache','Service-Worker-Allowed':'/','X-Content-Type-Options':'nosniff'})

    for leaf in ('manifest.webmanifest','icon.svg','icon-192.png','icon-512.png'):
        def public_endpoint(name):
            def public_file():return FileResponse(dist/name)
            return public_file
        app.add_api_route('/'+leaf,public_endpoint(leaf),methods=['GET'],include_in_schema=False)
    @app.get('/')
    def index():
        if not (dist/'index.html').is_file(): raise HTTPException(503,'Build the reader with npm run build --prefix reader')
        return FileResponse(dist/'index.html',headers={'Cache-Control':'no-store'})

    if (dist/'assets').is_dir(): app.mount('/assets',StaticFiles(directory=dist/'assets'),name='reader-assets')
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=5174)
    parser.add_argument('--library',type=Path,default=PROJECT/'library')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error('Port must be between 1024 and 65535')
    import uvicorn
    uvicorn.run(create_app(args.library,Path(os.environ.get('MANGAMOTION_RUNTIME',''))),host='127.0.0.1',port=args.port,proxy_headers=False)


if __name__ == '__main__': main()
