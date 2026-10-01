import copy
import unittest
from pipeline.motion.move_table import TABLE,recipe,finish_motion,speaker_follow
from pipeline.motion.solver import solve_camera,contains,interpolate
from pipeline.motion.comfort import audit_timeline
from pipeline.motion.compiler import compile_page,camera_record
from pipeline.director.validate import BEATS
from pipeline.adapters.director_base import fallback
from pipeline.store import read_json
from pathlib import Path


class MoveTests(unittest.TestCase):
    def test_every_beat_is_bounded_and_continuous_with_text(self):
        self.assertEqual(set(TABLE),set(BEATS))
        for beat in BEATS:
            tags={'beat':beat,'energy':.8,'shot':'closeup'};r=recipe(tags)
            event,audit=solve_camera([100,100,900,700],[[150,120,400,260]],[1000,800],recipe=r.move,
                                    duration=r.seconds,focus=[450,250,550,450],zoom=r.zoom,transient=r.transient)
            events=finish_motion(event,tags)
            metrics=audit_timeline(events,audit['protected'],audit['allowed'],[1000,800],800,r.transient)
            self.assertEqual(metrics['constraint_violations'],0)
            self.assertLessEqual(metrics['max_relative_scale'],1.4+1e-7)
            for segment in events:
                for i in range(101):
                    pose=interpolate(segment['from'],segment['to'],i/100)
                    self.assertTrue(contains(pose,[150,120,400,260]))
                    self.assertTrue(contains(audit['allowed'],pose))

    def test_future_follow_uses_line_starts_and_many_speakers_return_master(self):
        master=[0,0,100,100];frames={'b1':[0,0,95,100],'b2':[5,0,100,100]}
        lines=[{'t':2,'bubble':'b2','speaker':'c2'},{'t':.5,'bubble':'b1','speaker':'c1'}]
        events=speaker_follow(master,lines,frames)
        self.assertEqual([e['t'] for e in events],[.5,2]);self.assertEqual(events[0]['to'],frames['b1'])
        self.assertEqual(events[0]['dur'],.4)
        lines.append({'t':3,'bubble':'b1','speaker':'c3'})
        self.assertTrue(all(e['to']==master for e in speaker_follow(master,lines,frames)))

    def test_uncomfortable_target_falls_back_and_ambiguous_order_holds(self):
        root=Path(__file__).resolve().parents[1]
        page=read_json(root/'library/golden-m1d/chapter/analysis.json')['pages'][0]
        semantics=fallback(page,'test')
        for panel in semantics['panels']:panel.update(beat='impact',energy=1,shot='closeup')
        record=camera_record({**page,'semantics':semantics})
        record['order']['needs_review']=True
        result=compile_page(record,reading_wpm=240)
        self.assertTrue(all(e['move']=='hold' for p in result['panels'] for e in p['timeline']))
        self.assertTrue(all(a['constraint_violations']==0 for a in result['audit']))

    def test_comfort_rejects_discontinuous_and_fast_sustained_events(self):
        event,a=solve_camera([100,100,900,700],[],[1000,800],focus=[400,300,500,400],zoom=1.3,duration=4)
        bad={**event,'dur':.1}
        with self.assertRaises(ValueError):audit_timeline([bad],a['protected'],a['allowed'],[1000,800],800)
        jump={**event,'t':4,'from':[200,200,800,600]}
        with self.assertRaises(ValueError):audit_timeline([event,jump],a['protected'],a['allowed'],[1000,800],800)
