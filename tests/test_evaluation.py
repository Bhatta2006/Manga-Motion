import os,tempfile,shutil,unittest
from pathlib import Path
from pipeline.store import read_json
from pipeline.audio.evaluate import prepare
from pipeline.api.chapters import read_snapshot
from pipeline.store import ChapterStore


class EvaluationTests(unittest.TestCase):
    def test_anonymous_variants_keep_original_audio_and_reading_extents(self):
        source=Path(__file__).resolve().parents[1]/'library/golden-m1d/chapter'
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            library=Path(tmp)/'library';store=ChapterStore(library,'golden-m1d','chapter')
            for directory in ('pages','sfx'):shutil.copytree(source/directory,store.asset(directory))
            shutil.copyfile(source/'motionscript.json',store.asset('motionscript.json'))
            original=read_json(store.asset('motionscript.json'));result=prepare(library,'golden-m1d','chapter')
            self.assertEqual(len(result['samples']),3)
            original_panels=[p for page in original['pages'] for p in page['panels']]
            snapshots=set()
            for sample in result['samples']:
                self.assertFalse(any(label in sample['url'] for label in ('static','fixed','directed')))
                digest=sample['url'].split('snapshot=')[1].split('&')[0];snapshots.add(digest)
                script=read_snapshot(store,digest)['script'];panels=[p for page in script['pages'] for p in page['panels']]
                self.assertEqual([p['image'] for p in script['pages']],[p['image'] for p in original['pages']])
                for before,after in zip(original_panels,panels):
                    self.assertEqual([e for e in before['timeline'] if e['type']!='camera'],[e for e in after['timeline'] if e['type']!='camera'])
                    self.assertAlmostEqual(max(e['t']+e['dur'] for e in before['timeline'] if e['type']=='camera'),max(e['t']+e['dur'] for e in after['timeline'] if e['type']=='camera'))
                    self.assertEqual(before['transition_out']['dur'],after['transition_out']['dur'])
            self.assertEqual(len(snapshots),3)
