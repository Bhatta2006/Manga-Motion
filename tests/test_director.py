import copy
import os
import tempfile
import unittest
from pathlib import Path
from pipeline.adapters.director_base import fallback
from pipeline.director.validate import validate_output, output_schema
from pipeline.motion.compiler import camera_record,compile_page
from pipeline.runtime.scheduler import StageScheduler,StageExecutionError
from pipeline.cache import JsonStageCache,page_sha256
from pipeline.store import read_json
from pipeline.adapters.director_local import LocalQwenDirector
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]


class DirectorTests(unittest.TestCase):
    def setUp(self):self.page=copy.deepcopy(read_json(ROOT/'library/golden-m1d/chapter/analysis.json')['pages'][0])
    def test_ids_coordinates_enum_energy_and_missing_texts(self):
        base=fallback(self.page,'test');value={k:base[k] for k in ('summary','panels')}
        validate_output(value,self.page)
        mutations=[lambda v:v['panels'][0].update(bbox=[0,0,2,2]),
                   lambda v:v['panels'][0].update(id='invented'),
                   lambda v:v['panels'][0].update(energy=float('nan')),
                   lambda v:v['panels'][0]['texts'].clear(),
                   lambda v:v['panels'][0].update(beat='invented'),
                   lambda v:v['panels'][0]['focus'].append({'kind':'face','ref':'invented'})]
        for change in mutations:
            invalid=copy.deepcopy(value);change(invalid)
            with self.assertRaises(ValueError):validate_output(invalid,self.page)
        self.assertFalse(output_schema(self.page)['additionalProperties'])

    def test_human_labels_override_model_and_boxes_stay_original(self):
        semantic=fallback(self.page,'test')
        page={**self.page,'semantics':semantic,'characters':[]}
        record=camera_record(page,{'text_000':'dialogue'})
        self.assertEqual(record['texts'][0]['kind'],'dialogue')
        self.assertEqual(record['panels'],self.page['panels']);self.assertEqual(record['texts'][0]['bbox'],self.page['texts'][0]['bbox'])
        self.assertEqual(compile_page(record,reading_wpm=240)['panels'][0]['director']['beat'],'quiet')

    def test_verified_schema_wrapper_and_malformed_retry_flag(self):
        page=ROOT/'library/golden-m1d/chapter'/self.page['image']
        adapter=LocalQwenDirector({page_sha256(page):self.page})
        response=Mock();response.json.return_value={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]}
        adapter.client=Mock();adapter.client.post.return_value=response
        output=adapter.run_page(page)
        self.assertEqual(adapter.client.post.call_count,2);self.assertTrue(output['needs_review'])
        self.assertEqual(output['provider'],'safe-fallback')
        request=adapter.client.post.call_args.kwargs['json']
        self.assertEqual(request['response_format']['json_schema']['schema'],output_schema(self.page))
        self.assertEqual(request['temperature'],0)

    def test_dependent_summary_cache_sequence_and_cleanup(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            root=Path(tmp);paths=[root/f'{i}.page' for i in range(3)]
            for i,p in enumerate(paths):p.write_bytes(str(i).encode())
            class Adapter:
                stage_name='sequence';revision='1';heavy=True
                loads=unloads=0
                def load(self):self.loads+=1
                def unload(self):self.unloads+=1
                def run_page(self,p):return {'summary':p.read_text()}
            adapter=Adapter();scheduler=StageScheduler(root,JsonStageCache(root/'cache'))
            def run(seed=''):
                previous=[seed]
                return scheduler.run_sequence(adapter,paths,lambda p:{'previous':previous[0]},page_ready=lambda r:previous.__setitem__(0,r['summary']))
            _,first=run();_,warm=run()
            self.assertEqual(first['cache_hits'],0);self.assertEqual(warm['cache_hits'],3)
            self.assertEqual(adapter.loads,1);self.assertEqual(adapter.unloads,1)
            _,changed=run('new');self.assertEqual(changed['cache_hits'],2)
            self.assertEqual(adapter.loads,2);self.assertEqual(adapter.unloads,2)
            with self.assertRaises(StageExecutionError):
                scheduler.run_sequence(adapter,paths,lambda p:{'changed':True},page_ready=lambda r:(_ for _ in ()).throw(ValueError('invalid IDs')))
            self.assertEqual(adapter.loads,3);self.assertEqual(adapter.unloads,3)
