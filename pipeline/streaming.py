"""Validated ordered v2 prefixes, published after each directed page."""
from __future__ import annotations
import copy
import time
import os
from pathlib import Path
from pipeline.audio.scene import prepare_pages as prepare_sfx,append_events
from pipeline.audio.music import prepare_pages as prepare_music,attach as attach_music
from pipeline.adapters.music import MusicAdapter
from pipeline.cache import page_sha256, cache_key
from pipeline.ingest.hashes import object_hash
from pipeline.motion.compiler import compile_page, CameraAdapter, VerifiedCameraCache, camera_record
from pipeline.motion.pacing import configured_rate
from pipeline.motion.timing import PACING_REVISION, READING_KINDS, EXCLUDED_KINDS
from pipeline.motion.serialize import validate_contract
from pipeline.store import read_json, write_json
from pipeline.review.corrections import load as load_corrections,effective_page
from pipeline.layers.publish import attach as attach_layers


def streaming_record(store,job_id=None):
    record=read_json(store.asset('cache/stream-playback.json'))
    manifest=read_json(store.asset('import.json'))
    if not record or record.get('import_hash')!=object_hash(manifest):return None
    if job_id is not None and record.get('job_id')!=job_id:return None
    checksum=record.get('checksum')
    if checksum!=object_hash({k:v for k,v in record.items() if k!='checksum'}):return None
    return record


class StreamingPublisher:
    def __init__(self,store,manifest,*,validator=validate_contract,job_id=None):
        self.store,self.manifest,self.validator=store,manifest,validator
        self.import_hash=object_hash(manifest);self.rate=configured_rate(store)
        self.job_id=job_id
        self.layer_state=object_hash(read_json(store.asset('layer-enabled.json')))
        analysis=read_json(store.asset('analysis.json'))
        self.corrections=load_corrections(store,analysis) if analysis else {'pages':{}}
        labels_path=store.asset('pacing-labels.json');labels=read_json(labels_path)
        if labels_path.exists() and labels is None:raise ValueError('Pacing labels are damaged')
        if labels and labels.get('input_sha256')!=manifest['input_sha256']:raise ValueError('Pacing labels belong to an older import')
        self.labels=(labels or {}).get('pages',{})
        if not isinstance(self.labels,dict):raise ValueError('Invalid pacing labels')
        if set(self.labels)-{p['page_sha256'] for p in manifest['pages']}:raise ValueError('Unknown pacing label page')
        self.compilation_id=object_hash({'rate':self.rate,'labels':self.labels,'corrections':self.corrections,'layers':self.layer_state,'revision':CameraAdapter.revision,'music_revision':MusicAdapter(store).revision,'contract_version':2})
        retained=streaming_record(store,job_id)
        self.retained=retained if retained and retained.get('compilation_id')==self.compilation_id else None
        self.pending={};self.done=[];self.compiled=[];self.audit=[];self.music=[]
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
            labels=self.labels.get(digest,{})
            if not isinstance(labels,dict) or set(labels)-{t['id'] for t in current['texts']}:raise ValueError('Unknown pacing text label')
            if any(kind not in READING_KINDS|EXCLUDED_KINDS|{'unknown'} for kind in labels.values()):raise ValueError('Unknown pacing text kind')
            record=camera_record(effective_page(current,self.corrections),labels)
            config={'duration':2.0,'reading_wpm':self.rate,'pacing_revision':PACING_REVISION,
                    'page_inputs':{'analysis_sha256':object_hash(record)}}
            cache=VerifiedCameraCache(self.store.asset('cache/stages'))
            key=cache_key(digest,CameraAdapter.stage_name,CameraAdapter.revision,config)
            compiled=cache.read(CameraAdapter.stage_name,key)
            if compiled is None:
                compiled={**compile_page(record,reading_wpm=self.rate),'page_sha256':digest,'adapter_revision':CameraAdapter.revision}
                cache.write(CameraAdapter.stage_name,key,compiled)
            panels=copy.deepcopy(compiled['panels'])
            sounds,sound_metrics=prepare_sfx(self.store,{digest:record},[self.store.asset(entry['image'])],Path(os.environ['MANGAMOTION_RUNTIME']))
            append_events(panels,sounds[0])
            self.metrics.setdefault('sfx_stages',[]).append(sound_metrics)
            music,music_metrics=prepare_music(self.store,[{'id':entry['id'],**record}],[self.store.asset(entry['image'])],Path(os.environ['MANGAMOTION_RUNTIME']),
                                            previous=self.music[-1]['state'] if self.music else None)
            self.metrics.setdefault('music_stages',[]).append(music_metrics)
            for panel in panels:
                panel['id']=f'{entry["id"]}_{panel["id"]}'
                for focus in panel['director']['focus']:
                    if 'ref' in focus:focus['ref']=f'{entry["id"]}_{focus["ref"]}'
            candidate=self.compiled+[{'id':entry['id'],'image':entry['image'],'size':entry['size'],'panels':panels}]
            script={'version':1,'chapter':f'{self.store.series}/{self.store.chapter}',
                    'direction':self.manifest['settings']['direction'],'characters':{},'pages':candidate}
            script=attach_music(script,self.music+music)
            script=attach_layers(script,self.store,self.layer_state)
            self.validator(script)
            # Recheck all prefix assets: earlier bytes cannot be changed unnoticed.
            for earlier in self.manifest['pages'][:len(candidate)]:
                if page_sha256(self.store.asset(earlier['image']))!=earlier['page_sha256']:raise ValueError('Earlier streamed source changed')
            payload={'import_hash':self.import_hash,'script':script,'reading_wpm':self.rate,
                     'ready_pages':len(candidate),'total_pages':len(self.manifest['pages']),
                     'compilation_id':self.compilation_id,'job_id':self.job_id}
            payload['semantic_review_pages']=sum(bool(p.get('semantics',{}).get('needs_review')) for p in self.done+[current])
            payload['checksum']=object_hash(payload)
            if self.retained and len(candidate)<self.retained['ready_pages']:
                if script['pages']!=self.retained['script']['pages'][:len(candidate)] or any(self.retained['script'].get('scenes',{}).get(k)!=v for k,v in script['scenes'].items()):raise ValueError('Retried stream changed saved scenes')
            else:
                write_json(self.store.asset('cache/stream-playback.json'),payload)
            self.compiled=candidate;self.done.append(current)
            self.music+=music
            self.metrics['page_publish_seconds'].append(round(time.perf_counter()-started,6))
            self.metrics['ready_pages']=max(len(candidate),(self.retained or {}).get('ready_pages',0))
            if self.metrics['first_page_seconds'] is None:self.metrics['first_page_seconds']=round(time.perf_counter()-self.started,6)
