import copy
import json
import math
import os
import random
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.build_motion import build_motion
from pipeline.cache import page_sha256
from pipeline.motion.compiler import CameraAdapter, compile_page
from pipeline.motion.serialize import validate_contract, validate_geometry
from pipeline.motion.solver import contains, interpolate, solve_camera
from pipeline.motion.rules import safe_transition
from pipeline.motion.timing import timeline_duration
from pipeline.store import write_json

ROOT = Path(__file__).resolve().parents[1]


class CameraTests(unittest.TestCase):
    def test_continuous_bounds_on_random_and_edge_geometry(self):
        rng = random.Random(4050)
        cases = [([0, 0, 1000, 1400], []), ([0, 0, 50, 1400], [[0, 0, 80, 60]]),
                 ([400, 50, 450, 100], [[370, 50, 450, 110]])]
        for _ in range(150):
            x, y = rng.uniform(0, 850), rng.uniform(0, 1200)
            cases.append(([x, y, x + rng.uniform(1, 150), y + rng.uniform(1, 200)], []))
        for box, bubbles in cases:
            for recipe in ('push_in', 'pull_out', 'pan', 'hold'):
                event, audit = solve_camera(box, bubbles, [1000, 1400], recipe=recipe)
                self.assertLessEqual(audit['max_relative_scale'], 1.4)
                self.assertLessEqual(audit['max_zoom_rate_per_second'], .6)
                self.assertLessEqual(audit['max_pan_panel_widths_per_second'], 1.2)
                for i in range(101):
                    r = interpolate(event['from'], event['to'], (1-math.cos(math.pi*i/100))/2)
                    self.assertTrue(contains(audit['allowed'], r))
                    self.assertTrue(contains(r, audit['protected']))
                    center = [(audit['protected'][0]+audit['protected'][2])/2,
                              (audit['protected'][1]+audit['protected'][3])/2]
                    self.assertTrue(r[0]+.2*(r[2]-r[0]) <= center[0] <= r[0]+.8*(r[2]-r[0]))
                    self.assertTrue(r[1]+.2*(r[3]-r[1]) <= center[1] <= r[1]+.8*(r[3]-r[1]))

    def test_reject_invalid_geometry_before_output(self):
        for box in ([0,0,0,1], [0,0,1001,100], [0,0,float('nan'),100], [True,0,2,3], [0,0,10]):
            with self.assertRaises(ValueError): solve_camera(box, [], [1000,1400])
        for duration in (0, .2, float('inf'), True):
            with self.assertRaises(ValueError): solve_camera([0,0,100,100], [], [1000,1400], duration=duration)

    def test_order_and_ambiguity_gate(self):
        analysis = json.loads((ROOT/'library/golden-m1b/chapter/analysis.json').read_text())
        record = copy.deepcopy(analysis['pages'][0])
        record['order']['panel_ids'].reverse()
        compiled = compile_page(record)
        self.assertEqual([p['id'] for p in compiled['panels']], record['order']['panel_ids'])
        record['order']['needs_review'] = True
        self.assertTrue(all(p['timeline'][0]['move']=='hold' for p in compile_page(record)['panels']))
        record['order']['panel_ids'][0] = record['order']['panel_ids'][1]
        with self.assertRaises(ValueError): compile_page(record)

    def test_python_contract_and_failure_cases(self):
        original = json.loads((ROOT/'schema/examples/basic.json').read_text())
        self.assertEqual(validate_contract(original), {'version':1,'pages':1,'panels':1})
        with patch('pipeline.motion.serialize.subprocess.run',side_effect=FileNotFoundError('Node unavailable')):
            with self.assertRaisesRegex(ValueError,'validation unavailable'):validate_contract(original)
        mutations = [lambda p: p['bbox'].__setitem__(2,float('nan')),
                     lambda p: p['timeline'][0].__setitem__('dur',float('inf')),
                     lambda p: p['timeline'][0].__setitem__('from',[700,130,870,290]),
                     lambda p: p['timeline'][0].__setitem__('t',1),
                     lambda p: p['timeline'].append({**p['timeline'][0],'t':1}),
                     lambda p: p['timeline'][0].__setitem__('ease','invented'),
                     lambda p: p['timeline'][0].__setitem__('unexpected',True)]
        for mutation in mutations:
            script = copy.deepcopy(original); mutation(script['pages'][0]['panels'][0])
            with self.assertRaises(ValueError): validate_contract(script)
        script = copy.deepcopy(original); script['pages'][0]['image']='audio/wrong.wav'
        with self.assertRaises(ValueError): validate_contract(script)
        script = copy.deepcopy(original); script['pages'].append(copy.deepcopy(script['pages'][0]))
        with self.assertRaises(ValueError): validate_contract(script)

    def test_timing_retains_future_voice_and_sfx_clock_extents(self):
        self.assertEqual(timeline_duration([{'t':0,'type':'camera','dur':2}]),2.4)
        self.assertEqual(timeline_duration([{'t':2,'type':'line','dur':20}]),22.4)
        self.assertEqual(timeline_duration([{'t':1,'type':'sfx','file':'sfx/a.wav'}], {'sfx/a.wav':4}),5.4)

    def test_fast_transitions_cut_and_small_glides_remain_bounded(self):
        a={'to':[0,0,400,300]}
        cut,audit=safe_transition(a,{'from':[500,600,900,900]})
        self.assertEqual(cut,{'type':'cut','dur':0});self.assertFalse(audit['glide_allowed'])
        glide,audit=safe_transition(a,{'from':[5,5,405,305]})
        self.assertEqual(glide,{'type':'glide','dur':.4});self.assertLessEqual(audit['candidate_pan_rate'],1.2)
        cut,_=safe_transition(a,{'from':[5,5,405,305]},panel_widths=[1,1])
        self.assertEqual(cut,{'type':'cut','dur':0})

    def test_publication_cache_repair_and_stale_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime/tmp') as tmp:
            library = Path(tmp)/'library'; target=library/'test/ch01'
            target.mkdir(parents=True)
            source=ROOT/'library/golden-m1b/chapter'
            manifest=json.loads((source/'import.json').read_text()); analysis=json.loads((source/'analysis.json').read_text())
            manifest['pages']=manifest['pages'][:1];analysis['pages']=analysis['pages'][:1];analysis['chapter']='test/ch01'
            write_json(target/'import.json',manifest);write_json(target/'analysis.json',analysis)
            (target/'pages').mkdir()
            shutil.copyfile(source/manifest['pages'][0]['image'],target/manifest['pages'][0]['image'])
            args=(library,'test','ch01',Path(os.environ['MANGAMOTION_RUNTIME']))
            script,cold=build_motion(*args)
            digest=page_sha256(target/'motionscript.json')
            with patch.object(CameraAdapter,'run_page',side_effect=AssertionError('warm computation')):
                same,warm=build_motion(*args)
            self.assertEqual(cold['stage']['cache_hits'],0); self.assertEqual(warm['stage']['cache_hits'],1)
            self.assertEqual(script,same); self.assertEqual(page_sha256(target/'motionscript.json'),digest)
            artifact=next((target/'cache/stages/camera-solver').glob('*.json'))
            damaged=json.loads(artifact.read_text());damaged['panels'][0]['timeline'][0]['to'][0]=9999
            write_json(artifact,damaged)
            repaired,metrics=build_motion(*args)
            self.assertEqual(metrics['stage']['cache_hits'],0);self.assertEqual(repaired,script)
            with self.assertRaises(ValueError): build_motion(*args,validator=lambda s: (_ for _ in ()).throw(ValueError('rejected')))
            self.assertEqual(page_sha256(target/'motionscript.json'),digest)
            def mutate_input(script):
                modified=copy.deepcopy(analysis); modified['pages'][0]['review'].append({'reason':'external edit'})
                write_json(target/'analysis.json',modified)
                return {'version':1}
            with self.assertRaisesRegex(ValueError,'changed during compilation'):
                build_motion(*args,validator=mutate_input)
            self.assertEqual(page_sha256(target/'motionscript.json'),digest)
            analysis['direction']='ltr';write_json(target/'analysis.json',analysis)
            with self.assertRaises(ValueError): build_motion(*args)
            self.assertEqual(page_sha256(target/'motionscript.json'),digest)


if __name__=='__main__': unittest.main()
