import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_jobs_api import LocalClient
from pipeline.api.app import create_app
from pipeline.motion.pacing import pacing_labels
from pipeline.store import ChapterStore, write_json


class PacingAPITests(unittest.TestCase):
    def test_request_validation_origin_and_failed_compile(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            root=Path(tmp);runtime=root/'runtime';runtime.mkdir()
            client=LocalClient(create_app(root/'library',runtime,worker=False))
            for value in (True,79,601,240.0,'240'):
                self.assertEqual(client.post('/api/chapters/s/c/pacing',json={'reading_wpm':value}).status_code,422)
            self.assertEqual(client.post('/api/chapters/s/c/pacing',json={'reading_wpm':240,'extra':1}).status_code,422)
            self.assertEqual(client.post('/api/chapters/s/c/pacing',json={'reading_wpm':240},headers={'Origin':'https://foreign.test'}).status_code,403)
            with patch('pipeline.api.app.build_motion',side_effect=ValueError('stale input')):
                response=client.post('/api/chapters/s/c/pacing',json={'reading_wpm':240})
                self.assertEqual(response.status_code,409);self.assertIn('stale input',response.text)
            self.assertFalse((root/'library/s/pacing.json').exists())

    def test_labels_reject_wrong_hash_and_text(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as tmp:
            store=ChapterStore(Path(tmp),'s','c')
            analysis={'input_sha256':'current','pages':[{'page_sha256':'page','texts':[{'id':'text_000'}]}]}
            for value in ({'input_sha256':'stale','pages':{}},
                          {'input_sha256':'current','pages':{'page':{'bad':'dialogue'}}},
                          {'input_sha256':'current','pages':{'page':{'text_000':'invented'}}}):
                write_json(store.asset('pacing-labels.json'),value)
                with self.assertRaises(ValueError):pacing_labels(store,analysis)
