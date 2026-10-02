import unittest
import tempfile
from pathlib import Path
import numpy as np
from pipeline.layers.masks import inverse_envelope,uncovered,swept_guard,dilate,prepare_mask
from pipeline.adapters.segmenter import panel_for,MaskCache
from pipeline.layers.prepare import LayerCache
from pipeline.store import ChapterStore,write_json
from pipeline.ingest.hashes import object_hash

class LayerTests(unittest.TestCase):
    def test_inverse_envelope_covers_concavities_and_edge_anchors(self):
        subject=np.zeros((50,60),bool);subject[10:40,10:20]=True;subject[10:20,10:45]=True;subject[30:40,10:45]=True
        for anchor in ([30,25],[30,50],[0,25]):
            mask=inverse_envelope(subject,anchor,1.06)
            for s in np.linspace(1,1.06,137):self.assertEqual(uncovered(subject,mask,anchor,s),0)
        expected=np.zeros((9,9),bool);expected[2:7,2:7]=True
        seed=np.zeros((9,9),bool);seed[4,4]=True;self.assertTrue(np.array_equal(dilate(seed,2),expected))
    def test_swept_text_and_panel_guards_enclose_intervening_poses(self):
        mask=np.ones((8,8),bool);box=[10,10,18,18];poses=[{'scale':1,'offset':[0,0]},{'scale':1.06,'offset':[0,0]}]
        self.assertIsNone(swept_guard(mask,box,[.5,.5],poses,[0,0,30,30],[[22,22,25,25]]))
        self.assertEqual(swept_guard(mask,box,[.5,.5],poses,[0,0,30,30],[[18,12,22,16]]),'motion_intersects_protected_text')
        self.assertEqual(swept_guard(mask,box,[.5,.5],poses,[10,10,18,18],[]),'motion_crosses_panel')
        self.assertIsNone(panel_for([1,1,20,20],[{'id':'a','bbox':[0,0,3,3]}]))
    def test_clean_original_paper_proves_subject_but_unrelated_text_rejects(self):
        rgb=np.full((80,80,3),255,dtype='uint8');raw=np.zeros((20,20),bool);raw[4:16,4:16]=True;rgb[34:46,34:46]=0
        prepared,reason=prepare_mask(rgb,raw,[30,30,50,50],[0,0,80,80],[],[30,30,50,50]);self.assertIsNone(reason);self.assertEqual(prepared['audit']['max_uncovered_pixels'],0)
        _,reason=prepare_mask(rgb,raw,[30,30,50,50],[0,0,80,80],[[32,32,49,49]],[30,30,50,50]);self.assertEqual(reason,'motion_intersects_protected_text')
    def test_mask_asset_and_candidate_cache_tampering_cause_misses(self):
        with tempfile.TemporaryDirectory(dir=Path('D:/Motion Manga/.runtime/tmp')) as tmp:
            store=ChapterStore(Path(tmp),'test','chapter');asset=store.asset('layers/test.png');asset.parent.mkdir(parents=True);asset.write_bytes(b'mask')
            from pipeline.cache import page_sha256
            raw={'masks':[{'mask':'layers/test.png','mask_sha256':page_sha256(asset)}],'review':[]};raw['content_sha256']=object_hash(raw)
            cache=MaskCache(store.asset('cache'),store);cache.write('raw','key',raw);self.assertIsNotNone(cache.read('raw','key'))
            candidate={'accepted':[{'layer':{'mask':'layers/test.png','safety':{'mask_sha256':page_sha256(asset)}}}],'rejected':[]};candidate['content_sha256']=object_hash(candidate)
            other=LayerCache(store.asset('cache'),store);other.write('proof','key',candidate);self.assertIsNotNone(other.read('proof','key'))
            asset.write_bytes(b'tampered');self.assertIsNone(cache.read('raw','key'));self.assertIsNone(other.read('proof','key'))
if __name__=='__main__':unittest.main()
