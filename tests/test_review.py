import copy,os,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.api.app import create_app
from pipeline.review.corrections import effective_page,load,validate,recover
from pipeline.review.issues import review
from pipeline.ingest.hashes import object_hash
from pipeline.build_motion import build_motion
from tests.test_jobs_api import LocalClient
ROOT=Path(__file__).resolve().parents[1]

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['TEMP']);self.root=Path(self.temp.name);self.runtime=self.root/'runtime';self.runtime.mkdir()
        self.store=ChapterStore(self.root/'library','golden-m1d','chapter');source=ROOT/'library/golden-m1d/chapter'
        shutil.copytree(source,self.store.chapter_root)
        self.store.asset('corrections.json').unlink(missing_ok=True)
        self.analysis=read_json(self.store.asset('analysis.json'));self.before=read_json(self.store.asset('motionscript.json'))
        self.client=LocalClient(create_app(self.store.root,self.runtime,worker=False));self.url='/api/chapters/golden-m1d/chapter/review'
    def tearDown(self):self.temp.cleanup()
    def save(self,data,fix):return self.client.post(self.url,json={'expected_revision':data['revision'],'corrections':fix})
    def test_text_roundtrip_and_selective_cpu_cache_invalidation(self):
        before=self.client.get(self.url).json();fix=copy.deepcopy(before['corrections']);page=before['pages'][0];digest=page['page_sha256'];text=page['texts'][0]
        fix['pages'][digest]={'geometry_sha256':page['geometry_sha256'],'texts':{text['id']:{'text':'One two three four five six seven eight nine ten. '+self.root.name,'kind':'dialogue','confirmed':True}}}
        response=self.save(before,fix);self.assertEqual(response.status_code,200,response.text);data=response.json()
        self.assertEqual(data['metrics']['stage']['cache_hits'],4)
        self.assertEqual(data['metrics']['sfx_stage']['cache_hits'],4)
        self.assertEqual(data['metrics']['music_stage']['cache_hits'],4)
        self.assertEqual(data['pages'][0]['texts'][0]['text'],fix['pages'][digest]['texts'][text['id']]['text'])
        self.assertEqual(data['pages'][0]['texts'][0]['kind'],'dialogue')
        self.assertFalse(any(i['kind']=='text' and i['target']==text['id'] and i['page_sha256']==digest for i in data['issues']))
        self.assertEqual(read_json(self.store.asset('analysis.json')),self.analysis)
        self.assertEqual(read_json(self.store.asset('motionscript.json'))['pages'][1:],self.before['pages'][1:])
        repeated,metrics=build_motion(self.store.root,self.store.series,self.store.chapter,self.runtime)
        self.assertEqual(metrics['stage']['cache_hits'],5);self.assertEqual(repeated,read_json(self.store.asset('motionscript.json')))
        self.assertEqual(self.save(before,fix).status_code,409)
    def test_order_speaker_and_human_kind_survive_model_output(self):
        data=self.client.get(self.url).json();fix=copy.deepcopy(data['corrections']);page=data['pages'][0];digest=page['page_sha256'];text=page['texts'][0]
        fix['pages'][digest]={'geometry_sha256':page['geometry_sha256'],'texts':{text['id']:{'speaker':'narrator'}}}
        speaker=self.save(data,fix);self.assertEqual(speaker.status_code,200,speaker.text);data=speaker.json()
        for stage in ('stage','sfx_stage','music_stage'):self.assertEqual(data['metrics'][stage]['cache_hits'],5)
        order=list(reversed(page['order']));fix['pages'][digest]={'geometry_sha256':page['geometry_sha256'],'order':order,'order_confirmed':True,'texts':{text['id']:{'kind':'caption','speaker':'narrator'}}}
        response=self.save(data,fix);self.assertEqual(response.status_code,200,response.text)
        saved=response.json();self.assertEqual(saved['pages'][0]['order'],order);self.assertEqual(saved['pages'][0]['texts'][0]['kind'],'caption')
        self.assertEqual(saved['pages'][0]['texts'][0]['speaker'],'narrator');self.assertFalse(saved['voice_ready'])
        self.assertEqual([p['id'] for p in read_json(self.store.asset('motionscript.json'))['pages'][0]['panels']],['p0001_'+p for p in order])
    def test_stale_target_bad_shape_and_failed_publication_keep_old_pair(self):
        data=self.client.get(self.url).json();base=data['corrections'];digest=data['pages'][0]['page_sha256']
        for change in ({'pages':{'bad':{}}},{'input_sha256':'0'*64},{'pages':{digest:{'order':['missing']}}},{'pages':{digest:{'texts':{'missing':{'text':'bad'}}}}},{'version':2},{'extra':True}):
            response=self.save(data,{**base,**change});self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(read_json(self.store.asset('motionscript.json')),self.before)
        fix=copy.deepcopy(base);fix['pages'][digest]={'geometry_sha256':data['pages'][0]['geometry_sha256'],'texts':{data['pages'][0]['texts'][0]['id']:{'speaker':'eren'}}}
        changed=copy.deepcopy(self.analysis);changed['pages'][0]['texts'][0]['bbox'][0]+=1
        with self.assertRaisesRegex(ValueError,'geometry changed'):validate(fix,self.store,changed)
        with patch('pipeline.api.review.build_motion',side_effect=ValueError('deliberate publication failure')):
            response=self.save(data,fix);self.assertEqual(response.status_code,409)
        self.assertFalse(self.store.asset('corrections.json').exists());self.assertEqual(read_json(self.store.asset('motionscript.json')),self.before)
        self.assertEqual(read_json(self.store.asset('cache/review-transaction.json'))['state'],'rolled_back')
        self.assertEqual(self.client.post(self.url,json={'expected_revision':data['revision'],'corrections':base},headers={'Origin':'https://foreign.test'}).status_code,403)
    def test_pending_crash_recovery_and_source_crop_integrity(self):
        data=self.client.get(self.url).json();digest=data['pages'][0]['page_sha256'];page=self.analysis['pages'][0]
        url=self.url+'/pages/'+digest;self.assertEqual(self.client.get(url).content,self.store.asset(page['image']).read_bytes())
        write_json(self.store.asset('cache/review-transaction.json'),{'state':'pending','previous_corrections':None,'previous_script':self.before})
        write_json(self.store.asset('corrections.json'),data['corrections']);write_json(self.store.asset('motionscript.json'),{'damaged':True})
        response=self.client.get(self.url);self.assertEqual(response.status_code,200);self.assertEqual(read_json(self.store.asset('motionscript.json')),self.before)
        self.assertFalse(self.store.asset('corrections.json').exists())
        self.store.asset(page['image']).write_bytes(b'changed');self.assertEqual(self.client.get(url).status_code,409)

if __name__=='__main__':unittest.main()
