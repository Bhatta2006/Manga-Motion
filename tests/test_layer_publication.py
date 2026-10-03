import copy,os,shutil,tempfile,unittest
from pathlib import Path
from PIL import Image
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.layers.publish import attach,enable
from pipeline.api.chapters import snapshot,asset_response
from pipeline.cache import page_sha256
from pipeline.motion.serialize import validate_contract
ROOT=Path(__file__).resolve().parents[1]
class LayerPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['TEMP']);self.store=ChapterStore(Path(self.temp.name),'golden-m1d','chapter');shutil.copytree(ROOT/'library/golden-m1d/chapter',self.store.chapter_root);self.script=read_json(self.store.asset('motionscript.json'))
    def tearDown(self):self.temp.cleanup()
    def flat(self):
        script=copy.deepcopy(self.script)
        for p in script['pages']:
            for panel in p['panels']:panel.pop('layers',None)
        return script
    def test_enabled_real_candidate_roundtrips_and_stale_bindings_reject(self):
        self.assertEqual(attach(self.flat(),self.store),self.script);self.assertEqual(validate_contract(self.script)['version'],2)
        with self.assertRaisesRegex(ValueError,'Unknown or rejected'):enable(self.store,['rejected'])
        candidate=read_json(self.store.asset('cache/layer-candidates.json'));item=candidate['pages'][-1]['accepted'][0];item['layer']['poses'][1]['scale']=1.04;write_json(self.store.asset('cache/layer-candidates.json'),candidate)
        with self.assertRaisesRegex(ValueError,'candidate changed'):attach(self.flat(),self.store)
        self.assertEqual(read_json(self.store.asset('motionscript.json')),self.script)
    def test_changed_source_geometry_rejects_without_publishing(self):
        analysis=read_json(self.store.asset('analysis.json'));analysis['pages'][0]['panels'][0]['bbox'][0]+=1;write_json(self.store.asset('analysis.json'),analysis)
        with self.assertRaisesRegex(ValueError,'stale'):attach(self.flat(),self.store)
        self.assertEqual(read_json(self.store.asset('motionscript.json')),self.script)
    def test_snapshot_includes_verified_mask_and_rejects_wrong_alpha_dimensions(self):
        digest,record=snapshot(self.store,self.script);layer=self.script['pages'][-1]['panels'][0]['layers'][0]
        self.assertEqual(record['assets'][layer['mask']],layer['safety']['mask_sha256']);self.assertEqual(asset_response(self.store,digest,layer['mask']).body,self.store.asset(layer['mask']).read_bytes())
        invalid=copy.deepcopy(self.script);wrong=invalid['pages'][-1]['panels'][0]['layers'][0];wrong['mask']='layers/invalid.png';Image.new('RGBA',(1,1),(255,255,255,255)).save(self.store.asset(wrong['mask']));wrong['safety']['mask_sha256']=page_sha256(self.store.asset(wrong['mask']))
        with self.assertRaisesRegex(ValueError,'PNG alpha matching'):snapshot(self.store,invalid)
        self.assertEqual(read_json(self.store.asset('motionscript.json')),self.script)
if __name__=='__main__':unittest.main()
