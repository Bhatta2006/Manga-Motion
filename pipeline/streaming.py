"""Validated ordered v1 prefixes, published while the one OCR adapter is resident."""
from __future__ import annotations
import copy
import time
from pipeline.cache import page_sha256, cache_key
from pipeline.ingest.hashes import object_hash
from pipeline.motion.compiler import compile_page, CameraAdapter, VerifiedCameraCache
from pipeline.motion.pacing import configured_rate
from pipeline.motion.timing import PACING_REVISION, READING_KINDS, EXCLUDED_KINDS
from pipeline.motion.serialize import validate_contract
from pipeline.store import read_json, write_json


def streaming_record(store):
    record=read_json(store.asset('cache/stream-playback.json'))
    manifest=read_json(store.asset('import.json'))
    if not record or record.get('import_hash')!=object_hash(manifest):return None
    checksum=record.get('checksum')
    if checksum!=object_hash({k:v for k,v in record.items() if k!='checksum'}):return None
    return record


class StreamingPublisher:
    def __init__(self,store,manifest,*,validator=validate_contract):
        self.store,self.manifest,self.validator=store,manifest,validator
        self.import_hash=object_hash(manifest);self.rate=configured_rate(store)
        labels_path=store.asset('pacing-labels.json');labels=read_json(labels_path)
        if labels_path.exists() and labels is None:raise ValueError('Pacing labels are damaged')
        if labels and labels.get('input_sha256')!=manifest['input_sha256']:raise ValueError('Pacing labels belong to an older import')
        self.labels=(labels or {}).get('pages',{})
        if not isinstance(self.labels,dict):raise ValueError('Invalid pacing labels')
        if set(self.labels)-{p['page_sha256'] for p in manifest['pages']}:raise ValueError('Unknown pacing label page')
        self.compilation_id=object_hash({'rate':self.rate,'labels':self.labels,'revision':CameraAdapter.revision})
        retained=streaming_record(store)
        self.retained=retained if retained and retained.get('compilation_id')==self.compilation_id else None
        self.pending={};self.done=[];self.compiled=[];self.audit=[]
        self.metrics={'page_publish_seconds':[], 'first_page_seconds':None,'ready_pages':0}
        self.started=time.perf_counter()

    def publish(self,page):
        self.pending[page['id']]=page
        while len(self.done)<len(self.manifest['pages']):
            entry=self.manifest['pages'][len(self.done)]
            if entry['id'] not in self.pending:break
            current=self.pending.pop(entry['id'])
            started=time.perf_counter()
            if object_hash(read_json(self.store.asset('import.json')))!=self.import_hash:raise ValueError('Import changed during streaming')
            if any(current.get(k)!=entry[k] for k in ('id','image','size','page_sha256')):raise ValueError('Stream page/import mismatch')
            digest=entry['page_sha256']
            if page_sha256(self.store.asset(entry['image']))!=digest:raise ValueError('Source changed during streaming')
            record=copy.deepcopy({k:current[k] for k in ('size','panels','order','texts','review')})
            labels=self.labels.get(digest,{})
            if not isinstance(labels,dict) or set(labels)-{t['id'] for t in record['texts']}:raise ValueError('Unknown pacing text label')
            for text in record['texts']:
                if text['id'] in labels:
                    kind=labels[text['id']]
                    if kind not in READING_KINDS|EXCLUDED_KINDS|{'unknown'}:raise ValueError('Unknown pacing text kind')
                    text['kind']=kind
            config={'duration':2.0,'reading_wpm':self.rate,'pacing_revision':PACING_REVISION,
                    'page_inputs':{'analysis_sha256':object_hash(record)}}
            cache=VerifiedCameraCache(self.store.asset('cache/stages'))
            key=cache_key(digest,CameraAdapter.stage_name,CameraAdapter.revision,config)
            compiled=cache.read(CameraAdapter.stage_name,key)
            if compiled is None:
                compiled={**compile_page(record,reading_wpm=self.rate),'page_sha256':digest,'adapter_revision':CameraAdapter.revision}
                cache.write(CameraAdapter.stage_name,key,compiled)
            panels=copy.deepcopy(compiled['panels'])
            for panel in panels:
                panel['id']=f'{entry["id"]}_{panel["id"]}'
                for focus in panel['director']['focus']:
                    if 'ref' in focus:focus['ref']=f'{entry["id"]}_{focus["ref"]}'
            candidate=self.compiled+[{'id':entry['id'],'image':entry['image'],'size':entry['size'],'panels':panels}]
            script={'version':1,'chapter':f'{self.store.series}/{self.store.chapter}',
                    'direction':self.manifest['settings']['direction'],'characters':{},'pages':candidate}
            self.validator(script)
            # Recheck all prefix assets: earlier bytes cannot be changed unnoticed.
            for earlier in self.manifest['pages'][:len(candidate)]:
                if page_sha256(self.store.asset(earlier['image']))!=earlier['page_sha256']:raise ValueError('Earlier streamed source changed')
            payload={'import_hash':self.import_hash,'script':script,'reading_wpm':self.rate,
                     'ready_pages':len(candidate),'total_pages':len(self.manifest['pages']),
                     'compilation_id':self.compilation_id}
            payload['checksum']=object_hash(payload)
            if self.retained and len(candidate)<self.retained['ready_pages']:
                if candidate!=self.retained['script']['pages'][:len(candidate)]:raise ValueError('Retried stream changed saved scenes')
            else:
                write_json(self.store.asset('cache/stream-playback.json'),payload)
            self.compiled=candidate;self.done.append(current)
            self.metrics['page_publish_seconds'].append(round(time.perf_counter()-started,6))
            self.metrics['ready_pages']=max(len(candidate),(self.retained or {}).get('ready_pages',0))
            if self.metrics['first_page_seconds'] is None:self.metrics['first_page_seconds']=round(time.perf_counter()-self.started,6)
