"""Offline manifest uses sealed hashes; shell routes cannot expose arbitrary files."""
import os,shutil,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from pipeline.api.app import create_app
from pipeline.api.chapters import snapshot
from pipeline.store import ChapterStore
ROOT=Path(__file__).resolve().parents[1]
class OfflineAPITests(unittest.TestCase):
    def test_reader_build_changes_worker_shell_cache_identity(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            root=Path(tmp);runtime=root/'runtime';runtime.mkdir();dist=root/'dist';shutil.copytree(ROOT/'reader/dist',dist)
            with TestClient(create_app(root/'library',runtime,worker=False,dist=dist)) as client:
                before=client.get('/sw.js').text
                with (dist/'index.html').open('a',encoding='utf-8') as handle:handle.write('\n<!-- next build -->')
                after=client.get('/sw.js').text
                self.assertNotEqual(before.split("INDEX=")[0],after.split("INDEX=")[0])
                self.assertNotIn('__BUILD_ID__',after)
    def test_manifest_and_versioned_worker_are_bounded_to_sealed_assets(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            root=Path(tmp);library=root/'library';runtime=root/'runtime';runtime.mkdir()
            store=ChapterStore(library,'golden-m1d','chapter');shutil.copytree(ROOT/'library/golden-m1d/chapter',store.chapter_root)
            digest,record=snapshot(store)
            with TestClient(create_app(library,runtime,worker=False)) as client:
                response=client.get(f'/api/chapters/golden-m1d/chapter/playback/{digest}/manifest')
                self.assertEqual(response.status_code,200);self.assertEqual(response.json(),{'snapshot':digest,'assets':record['assets']})
                self.assertEqual(client.get('/api/chapters/golden-m1d/chapter/playback/'+'0'*64+'/manifest').status_code,409)
                worker=client.get('/sw.js');self.assertEqual(worker.status_code,200);self.assertNotIn('__BUILD_ID__',worker.text);self.assertNotIn('__SHELL_FILES__',worker.text);self.assertEqual(worker.headers['service-worker-allowed'],'/')
                self.assertIn('/assets/',worker.text);self.assertNotIn(str(store.chapter_root),worker.text)
                self.assertEqual(client.get('/icon.svg?leaf=../../.env').content,(ROOT/'reader/dist/icon.svg').read_bytes())
                self.assertEqual(client.get('/manifest.webmanifest?leaf=../../.env').json()['scope'],'/')
                self.assertEqual(client.get('/icon-192.png').content,(ROOT/'reader/dist/icon-192.png').read_bytes())
if __name__=='__main__':unittest.main()
