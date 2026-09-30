from __future__ import annotations

import sys
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw

from evaluate_m0a_ocr import edit_distance, words
from pipeline.adapters.baberu import _split_tall_crop, detection_fingerprint
from pipeline.runtime.scheduler import _reset_cuda_peaks


class OcrOptimizationTests(unittest.TestCase):
    def test_ocr_dependency_ignores_format_and_unrelated_boxes(self) -> None:
        first = {"adapter_revision": "pinned", "detections": {"texts": [[0, 1, 20, 30]], "panels": [[0, 0, 50, 50]]}}
        reformatted = json.loads(json.dumps(first, sort_keys=True, indent=4))
        self.assertEqual(detection_fingerprint(first), detection_fingerprint(reformatted))
        reformatted["detections"]["panels"] = [[0, 0, 80, 80]]
        self.assertEqual(detection_fingerprint(first), detection_fingerprint(reformatted))
        reformatted["detections"]["texts"][0][2] = 25
        self.assertNotEqual(detection_fingerprint(first), detection_fingerprint(reformatted))

    def test_error_metric_counts_insert_delete_substitute(self) -> None:
        self.assertEqual(edit_distance(words("THE LONGEST DREAM"), words("THE DREAM")), 1)
        self.assertEqual(edit_distance(words("EREN"), words("MIKASA")), 1)
        self.assertEqual(edit_distance(words("I DO"), words("YES I DO")), 1)
        self.assertEqual(words("DON’T YOU THINK, ASH?!"), words("don't you think ash"))

    def test_tall_split_preserves_all_pixels_and_avoids_ink(self) -> None:
        import numpy as np

        image = Image.new("RGB", (100, 300), "white")
        draw = ImageDraw.Draw(image)
        for row in (20, 70, 120, 170, 220, 270):
            draw.rectangle((20, row, 80, row + 10), fill="black")
        parts = _split_tall_crop(image)
        self.assertEqual(len(parts), 2)
        cut = parts[0][3]
        self.assertEqual(parts[1][1], cut)
        self.assertTrue((np.asarray(image)[cut - 1:cut + 2] == 255).all())
        rebuilt = Image.new("RGB", image.size)
        for box in parts:
            rebuilt.paste(image.crop(box), (box[0], box[1]))
        self.assertEqual(image.tobytes(), rebuilt.tobytes())
        solid = Image.new("RGB", image.size, "black")
        self.assertEqual(_split_tall_crop(solid), [(0, 0, 100, 300)])

    def test_cuda_peak_reset_happens_before_next_stage(self) -> None:
        events = []
        cuda = SimpleNamespace(is_available=lambda: True,
                               synchronize=lambda: events.append("sync"),
                               reset_peak_memory_stats=lambda: events.append("reset"))
        with patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=cuda)}):
            _reset_cuda_peaks()
        self.assertEqual(events, ["sync", "reset"])
