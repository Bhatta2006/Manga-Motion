import copy,os,tempfile,unittest,wave
from pathlib import Path
import numpy as np
from pipeline.audio.music_library import samples,PROFILES,AMBIENCE,LocalTonalLibrary,RATE
from pipeline.audio.music_cues import cues
from pipeline.audio.music import prepare_pages
from pipeline.store import ChapterStore

def record(moods):
    ids=[f'panel_{i}' for i in range(len(moods))]
    return {'id':'p001','order':{'panel_ids':ids},'semantics':{'summary':'School interior.',
            'panels':[{'id':i,'mood':m,'time_skip':False,'beat':'dialogue','energy':.2} for i,m in zip(ids,moods)]}}

class MusicTests(unittest.TestCase):
    def test_catalog_determinism_headroom_and_loop_seams(self):
        for bus,names in [('music',PROFILES),('ambience',AMBIENCE)]:
            for name in names:
                pcm=samples(bus,name)
                self.assertTrue(np.array_equal(pcm,samples(bus,name)))
                self.assertEqual(len(pcm),12*RATE);self.assertEqual(pcm[0],0);self.assertEqual(pcm[-1],0)
                self.assertLess(max(abs(pcm.astype(float))),32767*.751)
                self.assertLess(max(abs(int(pcm[1])),abs(int(pcm[-2]))),100)
                self.assertGreater(np.sqrt(np.mean(pcm.astype(float)**2)),100)
        with self.assertRaises(ValueError):samples('cloud','generated')

    def test_continuity_transient_mood_time_skip_and_unknown(self):
        output=cues(record([['calm'],['excited'],['calm'],['tense'],['tense']]))
        ids=[a['scene'] for a in output['assignments']]
        self.assertEqual(ids[0],ids[1]);self.assertEqual(ids[1],ids[2]);self.assertEqual(ids[2],ids[3]);self.assertNotEqual(ids[3],ids[4])
        self.assertEqual(len(output['new_scenes']),2)
        self.assertTrue(all(a['needs_review'] for a in output['assignments']))
        continuation=cues(record([[],['tense']]),output['state']);self.assertEqual(continuation['assignments'][0]['scene'],ids[-1])
        unknown=record([[]]);unknown['semantics']['panels'][0]['time_skip']=True
        self.assertIsNone(cues(unknown,output['state'])['assignments'][0]['scene'])
        self.assertIsNone(cues(record([[]]))['assignments'][0]['scene'])

    def test_causal_cache_and_asset_repair(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            root=Path(tmp);store=ChapterStore(root/'library','test','chapter');source=root/'page.txt';source.write_text('real hash input')
            page=record([['calm'],['calm']])
            out,cold=prepare_pages(store,[page],[source],root);_,warm=prepare_pages(store,[page],[source],root)
            self.assertEqual(warm['cache_hits'],1)
            self.assertTrue(out[0]['assets'][0]['license']);self.assertTrue(out[0]['assets'][0]['source'])
            path=store.asset(out[0]['assets'][0]['file']);original=path.read_bytes();path.write_bytes(b'corrupt')
            repaired,metrics=prepare_pages(store,[page],[source],root);self.assertEqual(metrics['cache_hits'],0);self.assertEqual(path.read_bytes(),original)
            changed=copy.deepcopy(page);changed['semantics']['panels'][0]['mood']=['sad']
            _,metrics=prepare_pages(store,[changed],[source],root);self.assertEqual(metrics['cache_hits'],0)
            with wave.open(str(path)) as f:self.assertEqual(f.getframerate(),RATE)
