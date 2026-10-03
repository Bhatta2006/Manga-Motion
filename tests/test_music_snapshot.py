"""Publication verifies real bed bytes/extents; immutable URLs detect tampering."""
import copy,os,shutil,tempfile,unittest
from pathlib import Path
from fastapi import HTTPException
from pipeline.store import ChapterStore,read_json
from pipeline.api.chapters import snapshot,asset_response,checked_asset
ROOT=Path(__file__).resolve().parents[1]

class MusicSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ['TEMP'])
        self.store=ChapterStore(Path(self.temp.name)/'library','golden-m1d','chapter')
        source=ROOT/'library/golden-m1d/chapter'
        for name in ('pages','sfx','music','ambience','layers'):shutil.copytree(source/name,self.store.asset(name))
        self.script=read_json(source/'motionscript.json')
    def tearDown(self):self.temp.cleanup()
    def test_verified_beds_serve_only_bound_hashes(self):
        digest,record=snapshot(self.store,self.script)
        bed=next(iter(self.script['scenes'].values()))['beds'][0]
        self.assertEqual(record['assets'][bed['file']],bed['sha256'])
        self.assertEqual(asset_response(self.store,digest,bed['file']).body,self.store.asset(bed['file']).read_bytes())
        self.store.asset(bed['file']).write_bytes(b'changed')
        with self.assertRaises(HTTPException) as error:asset_response(self.store,digest,bed['file'])
        self.assertEqual(error.exception.status_code,409)
        for relative in ('music/../.env','music/sub/path.wav','../music/test.wav'):
            with self.assertRaises(ValueError):checked_asset(self.store,relative)
    def test_wrong_hash_and_actual_audio_extent_rejected(self):
        for failure in ('hash','extent'):
            script=copy.deepcopy(self.script);bed=next(iter(script['scenes'].values()))['beds'][0]
            if failure=='hash':bed['sha256']='0'*64
            else:bed['duration']+=1;bed['loop'][1]+=1
            with self.assertRaisesRegex(ValueError,'hash mismatch|differs from actual'):snapshot(self.store,script)

if __name__=='__main__':unittest.main()
