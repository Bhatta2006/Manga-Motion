"""Swappable low-cost SFX provider, cached by source and directed-page inputs."""
from pipeline.audio.sfx_library import ProceduralSceneLibrary
from pipeline.audio.sfx_map import cues,REVISION
from pipeline.cache import JsonStageCache,page_sha256
from pipeline.ingest.hashes import object_hash


class SceneSfxAdapter:
    stage_name='scene-sfx';revision=f'{REVISION}-{ProceduralSceneLibrary.revision}';heavy=False
    def __init__(self,store,records,provider=None):
        self.store,self.records,self.provider=store,records,provider or ProceduralSceneLibrary()
        self.revision=f'{REVISION}-{self.provider.revision}'
    def load(self):pass
    def unload(self):pass
    def run_page(self,path):
        proposals,review=cues(self.records[page_sha256(path)]);assets={};events=[]
        for cue in proposals:
            category=cue['category']
            if category not in assets:assets[category]=self.provider.materialize(self.store,category)
            events.append({'panel_id':cue['panel_id'],'event':{'type':'sfx','t':cue['t'],'file':assets[category]['file'],'gain_db':cue['gain_db']},'audit':cue})
        value={'events':events,'assets':list(assets.values()),'review':review}
        return {**value,'content_sha256':object_hash(value)}


class VerifiedSfxCache(JsonStageCache):
    def __init__(self,root,store):super().__init__(root);self.store=store
    def read(self,stage,key):
        result=super().read(stage,key)
        if not result:return None
        try:
            if result['content_sha256']!=object_hash({k:result[k] for k in ('events','assets','review')}):return None
            for asset in result['assets']:
                path=self.store.asset(asset['file'])
                if not path.is_file() or page_sha256(path)!=asset['sha256']:return None
            return result
        except (ValueError,KeyError,TypeError,OSError):return None
