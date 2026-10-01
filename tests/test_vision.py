from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ingest_fixtures import ROOT, golden_pages
from pipeline.adapters.ocr import ChapterCropOcrAdapter
from pipeline.analyze_chapter import analyze_chapter
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.ingest.chapter import import_chapter
from pipeline.vision.order import reading_order
from pipeline.vision.panels import normalize_detections, union_area
from pipeline.vision.text import text_metadata
from pipeline.vision.evaluate import panel_matches, score_analysis


def detection(panels, texts=None, essential=None):
    return {"page_sha256": "hash", "adapter_revision": "fake-r1", "detections":
            {"panels": panels, "texts": texts or [], "characters": [], "tails": [],
             "is_essential_text": essential or []}}


class VisionTests(unittest.TestCase):
    def test_rtl_ltr_nested_columns_and_bands(self):
        # Tall column alongside two short panels, followed by a full-width row.
        boxes = [[0, 0, 45, 45], [55, 0, 100, 100], [0, 55, 45, 100], [0, 110, 100, 150]]
        self.assertEqual(reading_order(boxes, "rtl"), ([1, 0, 2, 3], []))
        self.assertEqual(reading_order(boxes, "ltr"), ([0, 2, 1, 3], []))

    def test_interlocking_order_and_no_panels_have_review_flags(self):
        order, reasons = reading_order([[0, 0, 80, 80], [20, 20, 100, 100]], "rtl")
        self.assertEqual(sorted(order), [0, 1])
        self.assertIn("ambiguous_panel_order", reasons)
        normalized = normalize_detections(detection([]), [100, 100], "rtl")
        self.assertEqual(normalized["order"]["panel_ids"], ["panel_000"])
        self.assertTrue(normalized["order"]["needs_review"])
        self.assertEqual(normalized["panels"][0]["origin"], "full_page_fallback")
        self.assertTrue(normalized["coverage"]["measured_from_fallback"])

    def test_union_coverage_overlap_and_nonfinite_geometry(self):
        boxes = [[0, 0, 80, 80], [20, 20, 100, 100]]
        self.assertEqual(union_area(boxes), 9200)
        raw = detection(boxes + [[float("nan"), 0, 3, 3], [-20, 0, 50, 50]], [[-0.5, 10, 30, 40]])
        result = normalize_detections(raw, [100, 100], "rtl")
        self.assertEqual(result["coverage"]["fraction"], .92)
        self.assertEqual(result["detections"]["texts"][0][0], 0)
        flags = {r["reason"] for r in result["review"]}
        self.assertTrue({"overlapping_panels", "nonfinite_box", "box_outside_page", "detector_edge_roundoff_clamped"} <= flags)
        json.dumps(result, allow_nan=False)
        small = normalize_detections(detection([[0, 0, 10, 10]]), [100, 100], "rtl")
        self.assertIn("panel_coverage_below_70_percent", {r["reason"] for r in small["review"]})

    def test_text_outside_panels_and_no_fabricated_semantic_class(self):
        raw = detection([[0, 0, 60, 100]], [[5, 5, 20, 20], [75, 5, 95, 30]], [True, True])
        normalized = normalize_detections(raw, [100, 100], "rtl")
        ocr = {"ocr": [{"text_index": i, "bbox": box, "text": "Hello\n world!", "status": "text_returned_unverified"}
                       for i, box in enumerate(raw["detections"]["texts"])]}
        result = text_metadata(normalized, ocr)
        self.assertEqual(result["texts"][0]["text"], "Hello world!")
        self.assertTrue(result["texts"][0]["reading_candidate"])
        self.assertEqual(result["texts"][0]["kind"], "unknown")
        self.assertIsNone(result["texts"][0]["confidence"])
        self.assertFalse(result["texts"][1]["reading_candidate"])
        self.assertIn("text_outside_detected_panels", result["texts"][1]["review_reasons"])

    def test_real_page_ocr_calls_only_recorded_text_crops(self):
        page = golden_pages()[0]
        digest = page_sha256(page)
        raw = detection([[0, 0, 1066, 1600]], [[40, 50, 140, 100], [300, 400, 500, 450]], [True, True])
        normalized = normalize_detections(raw, [1066, 1600], "rtl")
        normalized["page_sha256"] = digest
        adapter = ChapterCropOcrAdapter({digest: normalized})
        calls = []

        def engine(image, **kwargs):
            calls.append(image.size)
            return "crop text"

        adapter._engine = engine
        result = adapter.run_page(page)
        adapter.unload()
        self.assertEqual(calls, [(116, 66), (216, 66)])
        self.assertEqual(result["crop_audit"]["mode"], "detected-text-crops-only")

    def test_malformed_stage_json_is_a_miss(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime/tmp") as folder:
            cache = JsonStageCache(Path(folder))
            path = cache.write("stage", "key", {"valid": True})
            for invalid in ("{partial", "[]"):
                path.write_text(invalid, encoding="utf-8")
                self.assertIsNone(cache.read("stage", "key"))

    def test_full_page_text_detection_is_flagged_and_excluded(self):
        normalized = normalize_detections(detection([[0, 0, 100, 100]], [[1, 1, 99, 99]], [True]), [100, 100], "rtl")
        self.assertEqual(normalized["detections"]["texts"], [])
        self.assertIn("full_page_text_box_rejected", {r["reason"] for r in normalized["review"]})

    def test_matching_is_one_to_one_and_fallback_not_true_positive(self):
        expected = [{"id": "a", "bbox": [0, 0, 100, 100]}]
        observed = [{"id": "p1", "bbox": [0, 0, 100, 100]}, {"id": "p2", "bbox": [0, 0, 100, 100]}]
        self.assertEqual(len(panel_matches(expected, observed, .5)), 1)
        observed[0]["origin"] = "full_page_fallback"
        self.assertEqual(panel_matches(expected, observed[:1], .5), {})
        analysis = {"direction": "rtl", "pages": [{"id": "p", "page_sha256": "hash", "panels": observed,
                    "order": {"panel_ids": ["p1", "p2"]}, "texts": [], "coverage": {"fraction": 1}, "review": []}]}
        reference = {"method": "controlled error test", "iou_threshold": .5, "pages": [{"page_sha256": "hash", "direction": "rtl",
                     "panels": expected, "order": ["a"], "ocr": [{"text_index": 0, "category": "dialogue", "reference": "hello"}]}]}
        score = score_analysis(analysis, reference)
        self.assertEqual((score["panel_tp"], score["panel_fp"], score["panel_fn"]), (1, 1, 0))
        self.assertEqual(score["page_order_accuracy"], 0)
        self.assertEqual(score["dialogue_lexical_wer"], 1)
        self.assertEqual(score["missing_dialogue_crops"], 1)


class ChapterWiringTests(unittest.TestCase):
    def test_stage_residency_cache_direction_and_failure_publication(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime/tmp") as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            page = source / "page.jpg"
            page.write_bytes(golden_pages()[0].read_bytes())
            library = root / "library"
            import_chapter(source, library, "series", "chapter")
            active = []
            events = []

            class Detector:
                stage_name = "fake-chapter-detect"
                revision = "fake-r1"
                heavy = True

                def load(self):
                    self.assert_empty()
                    active.append("detector")
                    events.append("detector-load")

                def assert_empty(self):
                    if active:
                        raise AssertionError("Models overlap")

                def unload(self):
                    active.clear()
                    events.append("detector-unload")

                def run_page(self, page):
                    return detection([[0, 0, 500, 1600], [550, 0, 1066, 1600]], [[40, 50, 140, 100]], [True])

            class Ocr:
                stage_name = "fake-chapter-ocr"
                revision = "fake-ocr-r1"
                heavy = True
                fail = False

                def __init__(self, records, **kwargs):
                    self.records = records

                def load(self):
                    if active:
                        raise AssertionError("Models overlap")
                    active.append("ocr")
                    events.append("ocr-load")

                def unload(self):
                    active.clear()
                    events.append("ocr-unload")

                def run_page(self, page):
                    if self.fail:
                        raise RuntimeError("OCR deliberately failed")
                    raw = self.records[page_sha256(page)]
                    return {"image_size": raw["image_size"], "ocr": [{"text_index": 0, "bbox": raw["detections"]["texts"][0],
                            "crop_bbox": [32, 42, 148, 108], "text": "Hello", "status": "text_returned_unverified"}]}

            args = (library, "series", "chapter", Path(os.environ["MANGAMOTION_RUNTIME"]))
            first, cold = analyze_chapter(*args, detection_adapter=Detector(), ocr_factory=Ocr)
            self.assertEqual(events, ["detector-load", "detector-unload", "ocr-load", "ocr-unload"])
            again, warm = analyze_chapter(*args, detection_adapter=Detector(), ocr_factory=Ocr)
            self.assertEqual(first, again)
            self.assertTrue(all(m["cache_hits"] == 1 for m in warm["stages"]))
            self.assertEqual(len(events), 4)
            # Valid JSON with a mismatched cache identity is also a miss.
            cached = next((library / "series/chapter/cache/stages/fake-chapter-detect").glob("*.json"))
            bad = json.loads(cached.read_text())
            bad["page_sha256"] = "wrong-source"
            cached.write_text(json.dumps(bad), encoding="utf-8")
            _, repaired = analyze_chapter(*args, detection_adapter=Detector(), ocr_factory=Ocr)
            self.assertEqual([s["cache_hits"] for s in repaired["stages"]], [0, 1, 1, 1])
            self.assertEqual(events[-2:], ["detector-load", "detector-unload"])
            self.assertEqual(len(events), 6)
            import_chapter(source, library, "series", "chapter", {"direction": "ltr"})
            left, changed = analyze_chapter(*args, detection_adapter=Detector(), ocr_factory=Ocr)
            self.assertNotEqual(first["pages"][0]["order"]["panel_ids"], left["pages"][0]["order"]["panel_ids"])
            self.assertEqual([m["cache_hits"] for m in changed["stages"]], [1, 0, 1, 0])
            self.assertEqual(len(events), 6)
            output = library / "series/chapter/analysis.json"
            before = output.read_bytes()
            Ocr.fail = True
            Ocr.revision = "fake-ocr-failure"
            from pipeline.runtime.scheduler import StageExecutionError

            with self.assertRaisesRegex(StageExecutionError, "OCR deliberately failed"):
                analyze_chapter(*args, detection_adapter=Detector(), ocr_factory=Ocr)
            self.assertEqual(before, output.read_bytes())
            self.assertEqual(active, [])


if __name__ == "__main__":
    unittest.main()
