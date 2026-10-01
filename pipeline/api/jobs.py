"""Import request validation and durable job endpoints."""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from pipeline.db import JobConflict
from pipeline.ingest.chapter import validate_settings, DEFAULT_SETTINGS, is_link
from pipeline.store import ChapterStore


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    source: str = Field(min_length=1, max_length=2048)
    series: str = Field(min_length=1, max_length=64)
    chapter: str = Field(min_length=1, max_length=64)
    direction: Literal['rtl','ltr'] = 'rtl'


def router(jobs, library):
    routes = APIRouter()

    @routes.post('/api/imports', status_code=202)
    def create(request: ImportRequest):
        try:
            ChapterStore(library,request.series,request.chapter)
            for parent, label in ((library,request.series),(library/request.series,request.chapter)):
                if parent.is_dir() and any(p.name.casefold()==label.casefold() and p.name!=label for p in parent.iterdir()):
                    raise ValueError('Use the existing chapter/series capitalization to avoid Windows path aliases')
            source = Path(request.source)
            if not source.is_absolute() or source.drive.upper() != 'D:' or is_link(source):
                raise ValueError('Choose an absolute source path on D: without directory links')
            source = source.resolve()
            if source.drive.upper() != 'D:' or not source.exists():
                raise ValueError('Source does not exist on D:')
            if source.is_dir() and library.resolve().is_relative_to(source):
                raise ValueError('Source folder cannot contain the Library')
            # Preserve established series defaults, while this UI controls direction only.
            settings_path = ChapterStore(library,request.series,request.chapter).checked(library/request.series/'series.json')
            from pipeline.store import read_json
            saved = read_json(settings_path) or {}
            settings = validate_settings({**DEFAULT_SETTINGS, **saved.get('settings', {}), 'direction':request.direction})
            if settings['source_language'] != 'en':
                raise ValueError('This milestone supports English OCR only')
            return jobs.enqueue({'source':str(source), 'series':request.series,'chapter':request.chapter,'settings':settings})
        except JobConflict as exc:
            raise HTTPException(409,str(exc)) from exc
        except (ValueError,OSError) as exc:
            raise HTTPException(422,str(exc)) from exc

    @routes.get('/api/jobs/{job_id}')
    def get(job_id: str):
        job = jobs.get(job_id)
        if job is None: raise HTTPException(404,'Unknown job')
        return job

    @routes.post('/api/jobs/{job_id}/retry', status_code=202)
    def retry(job_id: str):
        try: return jobs.retry(job_id)
        except KeyError as exc: raise HTTPException(404,'Unknown job') from exc
        except JobConflict as exc: raise HTTPException(409,str(exc)) from exc

    return routes
