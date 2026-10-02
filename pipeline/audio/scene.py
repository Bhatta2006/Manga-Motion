from pipeline.adapters.scene_sfx import SceneSfxAdapter,VerifiedSfxCache
from pipeline.ingest.hashes import object_hash
from pipeline.runtime.scheduler import StageScheduler


def prepare_pages(store,records,paths,runtime,progress=None):
    adapter=SceneSfxAdapter(store,records)
    return StageScheduler(runtime,VerifiedSfxCache(store.asset('cache/stages'),store)).run_pages(
        adapter,paths,config={'policy':'restrained-local-scene-1'},
        page_configs={digest:{'analysis_sha256':object_hash(record)} for digest,record in records.items()},progress=progress)


def append_events(panels,sounds):
    lookup={p['id']:p for p in panels}
    for cue in sounds['events']:
        if cue['panel_id'] not in lookup:raise ValueError('Sound refers to unknown panel')
        lookup[cue['panel_id']]['timeline'].append(cue['event'].copy())
    for panel in panels:panel['timeline'].sort(key=lambda event:event['t'])
