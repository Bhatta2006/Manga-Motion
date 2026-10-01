import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from pipeline.streaming import StreamingPublisher, streaming_record
from pipeline.store import ChapterStore, read_json, write_json
from pipeline.api.chapters import playback_info, read_snapshot
from pipeline.runtime.scheduler import StageScheduler, StageExecutionError
from pipeline.cache import JsonStageCache

ROOT=Path(__file__).resolve().parents[1]


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['TEMP']);self.root=Path(self.temp.name)
        self.store=ChapterStore(self.root/'library','golden-m1d','chapter')
        source=ROOT/'library/golden-m1d/chapter'
        shutil.copytree(source/'pages',self.store.asset('pages'))
        self.manifest=read_json(source/'import.json');self.analysis=read_json(source/'analysis.json')
        write_json(self.store.asset('import.json'),self.manifest)
    def tearDown(self):self.temp.cleanup()

    def test_first_page_then_append_in_order_and_retry_retains_snapshot(self):
        publisher=StreamingPublisher(self.store,self.manifest)
        publisher.publish(self.analysis['pages'][1]);self.assertIsNone(streaming_record(self.store))
        publisher.publish(self.analysis['pages'][0]);first=streaming_record(self.store)
        self.assertEqual(first['ready_pages'],2);self.assertEqual(first['total_pages'],5)
        info=playback_info(self.store,stream=first)
        saved=read_snapshot(self.store,info['snapshot'])
        restarted=StreamingPublisher(self.store,self.manifest)
        restarted.publish(self.analysis['pages'][0])
        self.assertEqual(streaming_record(self.store)['ready_pages'],2)
        for page in self.analysis['pages'][1:3]:restarted.publish(page)
        later=streaming_record(self.store)
        self.assertEqual(later['ready_pages'],3)
        self.assertEqual(later['script']['pages'][:2],first['script']['pages'])
        self.assertEqual(read_snapshot(self.store,info['snapshot']),saved)
        self.assertFalse(self.store.asset('motionscript.json').exists())

    def test_failure_preserves_last_valid_prefix_and_corruption_rejected(self):
        publisher=StreamingPublisher(self.store,self.manifest)
        publisher.publish(self.analysis['pages'][0]);first=streaming_record(self.store)
        publisher.validator=lambda _:(_ for _ in ()).throw(ValueError('contract error'))
        with self.assertRaisesRegex(ValueError,'contract error'):publisher.publish(self.analysis['pages'][1])
        self.assertEqual(streaming_record(self.store),first)
        damaged=copy.deepcopy(first);damaged['ready_pages']=99
        write_json(self.store.asset('cache/stream-playback.json'),damaged)
        self.assertIsNone(streaming_record(self.store))

    def test_new_job_does_not_retain_previous_job_prefix(self):
        first=StreamingPublisher(self.store,self.manifest,job_id='old-job')
        for page in self.analysis['pages'][:2]:first.publish(page)
        self.assertIsNone(streaming_record(self.store,'new-job'))
        newer=StreamingPublisher(self.store,self.manifest,job_id='new-job')
        self.assertIsNone(newer.retained)
        newer.publish(self.analysis['pages'][0])
        self.assertEqual(streaming_record(self.store,'new-job')['ready_pages'],1)

    def test_changed_source_and_import_rejected(self):
        publisher=StreamingPublisher(self.store,self.manifest)
        page=self.analysis['pages'][0];self.store.asset(page['image']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Source changed'):publisher.publish(page)
        self.assertIsNone(streaming_record(self.store))

    def test_callback_on_cache_and_unload_on_callback_failure(self):
        page=self.store.asset(self.analysis['pages'][0]['image'])
        class Adapter:
            stage_name='stream-test';revision='1';heavy=True
            loads=unloads=0
            def load(self):self.loads+=1
            def unload(self):self.unloads+=1
            def run_page(self,_):return {'value':1}
        adapter=Adapter();scheduler=StageScheduler(self.root,JsonStageCache(self.root/'cache'));seen=[]
        scheduler.run_pages(adapter,[page],page_ready=seen.append)
        scheduler.run_pages(adapter,[page],page_ready=seen.append)
        self.assertEqual(len(seen),2);self.assertEqual(adapter.loads,1);self.assertEqual(adapter.unloads,1)
        with self.assertRaises(StageExecutionError):
            scheduler.run_pages(adapter,[page],config={'different':True},page_ready=lambda _:(_ for _ in ()).throw(ValueError('publish failed')))
        self.assertEqual(adapter.loads,2);self.assertEqual(adapter.unloads,2)
