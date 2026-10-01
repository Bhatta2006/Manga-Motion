"""One cached semantic call/page, sequential heavy stage, no cloud by default."""
from __future__ import annotations
import copy
import time
from pipeline.adapters.director_local import LocalQwenDirector
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.director.validate import validate_output
from pipeline.director.settings import series_notes
from pipeline.ingest.hashes import object_hash
from pipeline.runtime.scheduler import StageScheduler
from pipeline.store import ChapterStore, read_json, write_json


class DirectorCache(JsonStageCache):
    def __init__(self,root,records):super().__init__(root);self.records=records
    def read(self,stage,key):
        result=super().read(stage,key)
        if result is None:return None
        if result.get('provider')=='safe-fallback':return None
        try:
            value={k:result[k] for k in ('summary','panels')}
            if result.get('semantic_sha256')!=object_hash(value):return None
            validate_output(value,self.records[result['page_sha256']]);return result
        except (KeyError,ValueError,TypeError):return None


def direct_chapter(library,series,chapter,runtime,*,adapter_factory=LocalQwenDirector,progress=None,page_ready=None):
    store=ChapterStore(library,series,chapter)
    with store.lock():
        started=time.perf_counter();analysis=read_json(store.asset('analysis.json'));manifest=read_json(store.asset('import.json'))
        if not analysis or not manifest or analysis['input_sha256']!=manifest['input_sha256']:raise ValueError('Current chapter analysis is required')
        before=object_hash(analysis);records={};contexts={};paths={};notes=series_notes(store)
        for page in analysis['pages']:
            digest=page['page_sha256'];path=store.asset(page['image'])
            if page_sha256(path)!=digest:raise ValueError('Source changed before director')
            record=copy.deepcopy(page)
            if notes:record['series_notes']=notes
            geometry=read_json(store.asset(f'cache/pages/{digest}/geometry.json')) or {}
            boxes=geometry.get('detections',{}).get('characters',[])
            indices=geometry.get('source_indices',{}).get('characters',range(len(boxes)))
            record['characters']=[{'id':f'char_{index:03}','bbox':box} for index,box in zip(indices,boxes)]
            if digest in records:
                # Repeated art has one cached call. Distinct continuity contexts are
                # reviewable rather than silently claiming a new model inference.
                continue
            records[digest]=record;paths[digest]=path
        adapter=adapter_factory(records,contexts)
        previous=['']
        def prepare(path):
            digest=page_sha256(path);adapter.contexts[digest]=previous[0]
            return {'context_tokens':getattr(adapter,'spec',{}).get('context_tokens',8192),
                    'image_max_tokens':getattr(adapter,'spec',{}).get('image_max_tokens',256),
                    'analysis_sha256':object_hash(records[digest]),'previous_summary_sha256':object_hash(previous[0])}
        def ready(result):
            validate_output({k:result[k] for k in ('summary','panels')},records[result['page_sha256']])
            previous[0]=result['summary']
            if page_ready:
                for page in analysis['pages']:
                    if page['page_sha256']==result['page_sha256']:
                        page_ready({**copy.deepcopy(page),'semantics':result,
                                    'characters':records[result['page_sha256']]['characters']})
        outputs,stage=StageScheduler(runtime,DirectorCache(store.asset('cache/stages'),records)).run_sequence(
            adapter,list(paths.values()),prepare,progress=progress,page_ready=ready)
        mapped=dict(zip(paths,outputs))
        if object_hash(read_json(store.asset('analysis.json')))!=before:raise ValueError('Analysis changed during director')
        if notes!=series_notes(store):raise ValueError('Director notes changed during processing')
        for digest,path in paths.items():
            if page_sha256(path)!=digest:raise ValueError('Source changed during director')
        value={'analysis_sha256':before,'notes_sha256':object_hash(notes),'pages':[{ 'page_sha256':p['page_sha256'],
              'semantics':mapped[p['page_sha256']], 'characters':records[p['page_sha256']]['characters']} for p in analysis['pages']],
               'continuity_note':'Previous generated page summary is carried forward and included in cache identity. Repeated source hashes reuse the first context; repeated-page semantics require review.'}
        write_json(store.asset('cache/director.json'),value)
        return value,{'stage':stage,'elapsed_seconds':round(time.perf_counter()-started,6),
                      'review_pages':sum(p['semantics']['needs_review'] for p in value['pages']),
                      'cloud_calls':0,'api_cost':0}
