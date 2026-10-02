"""Replaceable CPU tonal library, through the existing page stage scheduler."""
from pipeline.audio.music_library import LocalTonalLibrary
from pipeline.audio.music_cues import cues,REVISION
from pipeline.cache import JsonStageCache,page_sha256
from pipeline.ingest.hashes import object_hash

class MusicAdapter:
    stage_name='scene-music';heavy=False
    def __init__(self,store,provider=None):
        self.store,self.provider=store,provider or LocalTonalLibrary()
        self.revision=f'{REVISION}-{self.provider.revision}'
        self.record=None;self.previous=None
    def load(self):pass
    def unload(self):pass
    def run_page(self,path):
        mapped=cues(self.record,self.previous);scenes={};assets={}
        for scene_id,scene in mapped['new_scenes'].items():
            beds=[]
            for bus,key in (('music','profile'),('ambience','ambience')):
                if not scene[key]:continue
                asset=self.provider.materialize(self.store,bus,scene[key]);assets[asset['file']]=asset
                beds.append({'id':f'{bus}_{scene[key]}','bus':bus,'file':asset['file'],'sha256':asset['sha256'],'duration':asset['duration'],
                             'loop':asset['loop'],'gain_db':-22 if bus=='music' else -28,'fade_seconds':.8,'duck_db':-8 if bus=='music' else -6})
            scenes[scene_id]={'mood':scene['mood'],'beds':beds}
        value={'assignments':mapped['assignments'],'scenes':scenes,'state':mapped['state'],'review':mapped['review'],'assets':list(assets.values())}
        return {**value,'content_sha256':object_hash(value)}

class MusicCache(JsonStageCache):
    def __init__(self,root,store):super().__init__(root);self.store=store
    def read(self,stage,key):
        result=JsonStageCache.read(self,stage,key)
        if not result:return None
        try:
            if result['content_sha256']!=object_hash({k:result[k] for k in ('assignments','scenes','state','review','assets')}):return None
            if any(page_sha256(self.store.asset(a['file']))!=a['sha256'] for a in result['assets']):return None
            return result
        except (ValueError,KeyError,TypeError,OSError):return None
