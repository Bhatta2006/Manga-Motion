import copy,os,tempfile,unittest
from pathlib import Path
import numpy as np
from pipeline.audio.sfx_library import samples,ProceduralSceneLibrary
from pipeline.audio.sfx_map import cues,CATEGORIES
from pipeline.adapters.director_base import fallback
from pipeline.motion.compiler import camera_record
from pipeline.adapters.scene_sfx import SceneSfxAdapter,VerifiedSfxCache
from pipeline.runtime.scheduler import StageScheduler
from pipeline.store import ChapterStore,read_json

ROOT=Path(__file__).resolve().parents[1]


class SceneSoundTests(unittest.TestCase):
    def test_catalog_is_deterministic_no_clipping_and_silent_edges(self):
        for category in CATEGORIES:
            pcm=samples(category)
            self.assertTrue(np.array_equal(pcm,samples(category)))
            self.assertEqual(pcm[0],0);self.assertEqual(pcm[-1],0)
            self.assertGreater(float(np.sqrt(np.mean(pcm.astype(float)**2))),1)
            self.assertLessEqual(max(abs(pcm.astype(float))),32767*.321)
        with self.assertRaises(ValueError):samples('page-turn')

    def test_nonreading_text_conflict_and_restrained_scene_fallback(self):
        page=read_json(ROOT/'library/golden-m1d/chapter/analysis.json')['pages'][0]
        semantic=fallback(page,'test');semantic['summary']='Two people in a grassy field.'
        first=semantic['panels'][0]
        first['sfx']=[{'category':'whoosh','text_id':first['texts'][0]['id']}]
        record=camera_record({**page,'semantics':semantic},{first['texts'][0]['id']:'nonverbal'})
        output,review=cues(record)
        self.assertEqual(output[0]['category'],'wind');self.assertEqual(review[0]['reason'],'sfx_cue_conflicts_with_text_class')
        for panel in record['semantics']['panels']:panel.update(beat='impact',energy=1,sfx=[])
        output,review=cues(record);self.assertEqual(len(output),3);self.assertTrue(review)

    def test_assets_have_provenance_and_corruption_invalidates_only_dependent_page(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            store=ChapterStore(Path(tmp)/'library','test','chapter')
            library=ProceduralSceneLibrary();asset=library.materialize(store,'chime')
            self.assertTrue(asset['license']);self.assertTrue(asset['source'])
            before=store.asset(asset['file']).read_bytes();store.asset(asset['file']).write_bytes(b'bad')
            restored=library.materialize(store,'chime');self.assertEqual(store.asset(restored['file']).read_bytes(),before)
            page=read_json(ROOT/'library/golden-m1d/chapter/analysis.json')['pages'][0]
            semantic=fallback(page,'test');semantic['summary']='A grassy field.'
            record=camera_record({**page,'semantics':semantic})
            adapter=SceneSfxAdapter(store,{page['page_sha256']:record})
            cache=VerifiedSfxCache(store.asset('cache/stages'),store);scheduler=StageScheduler(Path(tmp),cache)
            source=ROOT/'library/golden-m1d/chapter'/page['image']
            first,metrics=scheduler.run_pages(adapter,[source]);_,warm=scheduler.run_pages(adapter,[source])
            self.assertEqual(warm['cache_hits'],1)
            store.asset(first[0]['assets'][0]['file']).write_bytes(b'damaged')
            _,repair=scheduler.run_pages(adapter,[source]);self.assertEqual(repair['cache_hits'],0)
