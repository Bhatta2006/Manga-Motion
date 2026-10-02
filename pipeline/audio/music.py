"""Causal page preparation; prefix and complete chapter use identical cache inputs."""
import copy
from pipeline.adapters.music import MusicAdapter,MusicCache
from pipeline.runtime.scheduler import StageScheduler
from pipeline.ingest.hashes import object_hash

def prepare_pages(store,records,paths,runtime,progress=None,previous=None):
    if len(records)!=len(paths):raise ValueError('Music records/assets mismatch')
    adapter=MusicAdapter(store);state=copy.deepcopy(previous);position=0
    def prepare(path):
        nonlocal position
        adapter.record=records[position];adapter.previous=state;position+=1
        return {'analysis_sha256':object_hash(adapter.record),'previous_state':state}
    def completed(output):
        nonlocal state
        state=output['state']
    return StageScheduler(runtime,MusicCache(store.asset('cache/stages'),store)).run_sequence(adapter,paths,prepare,progress=progress,page_ready=completed)

def attach(script,outputs):
    if len(script['pages'])!=len(outputs):raise ValueError('Music page count mismatch')
    result=copy.deepcopy(script);result['version']=2;result['scenes']={}
    for page,output in zip(result['pages'],outputs):
        result['scenes'].update(output['scenes'])
        cues={c['panel_id']:c for c in output['assignments']}
        for panel in page['panels']:
            local=panel['id'][len(page['id'])+1:]
            if local not in cues:raise ValueError('Music refers to unknown panel')
            if cues[local]['scene']:panel['scene']=cues[local]['scene']
    return result
