import unittest
from pipeline.motion.timing import reading_budget, timeline_duration
from pipeline.motion.compiler import compile_page


def text(words, kind='dialogue', **extra):
    return {'id':'text_0', 'text':' '.join(['word']*words), 'kind':kind, **extra}


class ReadingTests(unittest.TestCase):
    def test_word_growth_and_no_dense_cap(self):
        times=[reading_budget([text(n)] if n else [])['seconds'] for n in (0,10,40,100)]
        self.assertEqual(times,sorted(times));self.assertEqual(len(set(times)),4)
        self.assertGreater(times[-1],12)
        self.assertGreater(reading_budget([text(40)],160)['seconds'],reading_budget([text(40)],320)['seconds'])

    def test_only_dialogue_caption_known_words_and_uncertainty(self):
        for kind in ('sfx','watermark','translator_note','sign','nonverbal'):
            budget=reading_budget([text(100,kind)])
            self.assertEqual(budget['words'],0);self.assertEqual(budget['seconds'],2.4)
        self.assertEqual(reading_budget([text(10,'caption')])['words'],10)
        unknown=reading_budget([text(40,'unknown')])
        self.assertEqual(unknown['words'],0);self.assertEqual(unknown['estimated_unknown_words'],40)
        self.assertTrue(unknown['needs_review']);self.assertGreater(unknown['seconds'],12)
        self.assertFalse(reading_budget([text(10,'unknown',is_essential=False)])['needs_review'])

    def test_failed_crop_differs_from_empty_panel(self):
        self.assertEqual(reading_budget([])['seconds'],2.4)
        self.assertGreaterEqual(reading_budget([text(0,'unknown')])['seconds'],6)
        self.assertTrue(reading_budget([text(0)])['needs_review'])
        for rate in (True,79,601,240.0,float('nan')):
            with self.assertRaises(ValueError):reading_budget([],rate)

    def test_future_speech_and_music_policy(self):
        events=[{'type':'camera','t':0,'dur':2},{'type':'line','t':1,'dur':3,'audio':'audio/a.wav'}]
        self.assertEqual(timeline_duration(events,{'audio/a.wav':10}),11.4)
        self.assertEqual(timeline_duration(events+[{'type':'music','t':0,'dur':600}],{'audio/a.wav':10}),11.4)

    def test_reading_hold_is_continuous_and_keeps_camera_speed(self):
        record={'size':[100,100], 'panels':[{'id':'p','bbox':[0,0,100,100],'origin':'detected'}],
                'order':{'panel_ids':['p'],'needs_review':False},'review':[],
                'texts':[{**text(100),'panel_id':'p','bbox':[10,10,90,30]}]}
        result=compile_page(record,reading_wpm=240)
        camera,hold=result['panels'][0]['timeline']
        self.assertEqual(camera['dur'],2);self.assertEqual(hold['t'],2)
        self.assertEqual(camera['to'],hold['from']);self.assertEqual(hold['from'],hold['to'])
        self.assertAlmostEqual(timeline_duration([camera,hold]),27.4)
