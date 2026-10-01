from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import pypdfium2 as pdfium
from PIL import Image

from ingest_fixtures import ROOT, build_fixtures, golden_pages
from pipeline.cache import page_sha256
from pipeline.ingest import ImportFailure
from pipeline.ingest.archive import natural_key
from pipeline.ingest.chapter import import_chapter
from pipeline.ingest.pages import raster_info
from pipeline.store import ChapterStore


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime/tmp")
        cls.root = Path(cls.temp.name)
        cls.folder, cls.cbz, cls.pdf = build_fixtures(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.library = Path(self.work.name) / "library"

    def run_import(self, source: Path | None = None, overrides: dict | None = None):
        return import_chapter(source or self.folder, self.library, "golden", "chapter", overrides)

    def test_folder_and_cbz_original_bytes_pixels_and_order(self) -> None:
        for index, source in enumerate([self.folder, self.cbz]):
            manifest, metrics = import_chapter(source, self.library, "golden", f"c{index}")
            self.assertEqual((len(manifest["pages"]), metrics["cache_misses"]), (5, 5))
            root = self.library / "golden" / f"c{index}"
            for original, page in zip(golden_pages(), manifest["pages"]):
                self.assertEqual(original.read_bytes(), (root / page["original"]).read_bytes())
                self.assertEqual(original.read_bytes(), (root / page["image"]).read_bytes())
                self.assertEqual(raster_info(original)["pixel_sha256_rgb"], page["pixel_sha256_rgb"])
            if source == self.cbz:
                container = manifest["source_container"]
                self.assertEqual(source.read_bytes(), (root / container["file"]).read_bytes())
                self.assertEqual(manifest["ignored_files"], ["notes.txt"])

    def test_pdf_lossless_render_and_original_preservation(self) -> None:
        manifest, metrics = self.run_import(self.pdf)
        root = self.library / "golden/chapter"
        self.assertEqual(metrics["cache_misses"], 5)
        self.assertEqual(self.pdf.read_bytes(), (root / manifest["source_container"]["file"]).read_bytes())
        document = pdfium.PdfDocument(self.pdf)
        try:
            document.init_forms()
            for index, page_record in enumerate(manifest["pages"]):
                page = document[index]
                bitmap = page.render(scale=2, fill_color=(255, 255, 255, 255))
                image = bitmap.to_pil()
                try:
                    with image.convert("RGB") as expected, Image.open(root / page_record["image"]) as served:
                        with served.convert("RGB") as actual:
                            self.assertEqual(expected.size, actual.size)
                            self.assertEqual(expected.tobytes(), actual.tobytes())
                    with Image.open(golden_pages()[index]) as original:
                        self.assertEqual(list(original.size), page_record["size"])
                finally:
                    image.close()
                    bitmap.close()
                    page.close()
        finally:
            document.close()

    def test_lossless_tiff_derivative_preserves_source_pixels(self) -> None:
        folder = Path(self.work.name) / "tiff"
        folder.mkdir()
        source = folder / "page.tiff"
        with Image.open(golden_pages()[0]) as image:
            image.save(source, format="TIFF", compression="tiff_lzw")
        original_bytes = source.read_bytes()
        manifest, _ = self.run_import(folder)
        record = manifest["pages"][0]
        root = self.library / "golden/chapter"
        self.assertEqual(original_bytes, (root / record["original"]).read_bytes())
        self.assertTrue(record["image"].endswith(".png"))
        self.assertEqual(raster_info(source)["pixel_sha256_rgb"], raster_info(root / record["image"])["pixel_sha256_rgb"])
        self.assertEqual(record["fidelity"], "pixel-identical-lossless-derivative")

    def test_pdf_resolution_invalidates_and_dimension_limit_precedes_render(self) -> None:
        full, _ = self.run_import(self.pdf)
        half, metrics = self.run_import(self.pdf, {"pdf_dpi": 72})
        self.assertEqual(metrics["cache_misses"], 5)
        for first, second in zip(full["pages"], half["pages"]):
            self.assertNotEqual(first["page_sha256"], second["page_sha256"])
            self.assertEqual(second["size"], [(v + 1) // 2 for v in first["size"]])
        before = (self.library / "golden/chapter/import.json").read_bytes()
        with patch("pipeline.ingest.pdf.MAX_PIXELS", 100), patch.object(pdfium.PdfPage, "render", side_effect=AssertionError("allocated oversized bitmap")):
            with self.assertRaisesRegex(ImportFailure, "page-1.*dimensions exceed"):
                self.run_import(self.pdf, {"pdf_dpi": 200})
        self.assertEqual(before, (self.library / "golden/chapter/import.json").read_bytes())

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_folder_reparse_points_are_rejected(self) -> None:
        folder = Path(self.work.name) / "linked-folder"
        folder.mkdir()
        link = folder / "loop"
        assert folder.resolve().is_relative_to(ROOT.resolve())
        subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(folder)],
                       check=True, capture_output=True)
        try:
            with self.assertRaisesRegex(ImportFailure, "Linked folder entry.*loop"):
                self.run_import(folder)
        finally:
            # Remove only the junction, never recursively delete its target.
            link.rmdir()

    def test_warm_reuse_skips_decode_and_pdf_render(self) -> None:
        for index, source in enumerate([self.folder, self.cbz, self.pdf]):
            args = (source, self.library, "golden", f"warm{index}")
            first, _ = import_chapter(*args)
            with patch("pipeline.ingest.pages.raster_info", side_effect=AssertionError("decoded warm image")), patch("pipeline.ingest.pdf.PdfiumRasterizer.render", side_effect=AssertionError("rendered warm PDF")):
                again, metrics = import_chapter(*args)
            self.assertEqual(first, again)
            self.assertEqual((metrics["cache_hits"], metrics["cache_misses"]), (5, 0))

    def test_settings_change_invalidates_cache_and_persists_per_series(self) -> None:
        first, _ = self.run_import()
        changed, metrics = self.run_import(overrides={"direction": "ltr", "target_language": "ja"})
        self.assertNotEqual(first["input_sha256"], changed["input_sha256"])
        self.assertEqual(metrics["cache_misses"], 5)
        self.assertEqual([p["page_sha256"] for p in first["pages"]], [p["page_sha256"] for p in changed["pages"]])
        again, metrics = self.run_import()
        self.assertEqual(changed, again)
        self.assertEqual(metrics["cache_hits"], 5)

    def test_missing_corrupt_page_and_cache_are_repaired(self) -> None:
        manifest, _ = self.run_import()
        root = self.library / "golden/chapter"
        (root / manifest["pages"][0]["image"]).unlink()
        (root / manifest["pages"][1]["image"]).write_bytes(b"bad page")
        key = manifest["pages"][2]["cache_key"]
        (root / f"cache/ingest/{key}.json").write_text("invalid JSON", encoding="utf-8")
        again, metrics = self.run_import()
        self.assertEqual(manifest, again)
        self.assertEqual((metrics["cache_hits"], metrics["cache_misses"]), (2, 3))

    def test_source_change_invalidates_only_changed_page(self) -> None:
        manifest, _ = self.run_import()
        source = self.folder / "page-1.jpg"
        original = source.read_bytes()
        try:
            source.write_bytes(original + b"\nprivate-cache-invalidation-fixture")
            changed, metrics = self.run_import()
            self.assertNotEqual(manifest["input_sha256"], changed["input_sha256"])
            self.assertEqual((metrics["cache_hits"], metrics["cache_misses"]), (4, 1))
            self.assertEqual(manifest["pages"][0]["pixel_sha256_rgb"], changed["pages"][0]["pixel_sha256_rgb"])
        finally:
            source.write_bytes(original)

    def test_failure_names_page_preserves_manifest_and_resumes(self) -> None:
        manifest, _ = self.run_import()
        source = self.folder / "page-3.jpg"
        original = source.read_bytes()
        manifest_path = self.library / "golden/chapter/import.json"
        before = manifest_path.read_bytes()
        try:
            source.write_bytes(b"not an image")
            with self.assertRaisesRegex(ImportFailure, "page-3.jpg"):
                self.run_import(overrides={"direction": "ltr"})
            self.assertEqual(manifest_path.read_bytes(), before)
        finally:
            source.write_bytes(original)
        _, metrics = self.run_import(overrides={"direction": "ltr"})
        self.assertEqual((metrics["cache_hits"], metrics["cache_misses"]), (2, 3))
        self.assertEqual(manifest["settings"]["direction"], "rtl")

    def test_archive_rejects_traversal_links_duplicates_and_bombs(self) -> None:
        cases = ["../page.jpg", "/page.jpg", "C:/page.jpg", "a\\page.jpg", "a/../page.jpg"]
        for name in cases:
            archive = self.root / "bad.cbz"
            with ZipFile(archive, "w") as handle:
                handle.writestr(name, b"private bytes")
            if "\\" in name:
                # ZipInfo normalizes backslashes while writing on Windows.
                # Patch both filename headers to exercise an actual unsafe input.
                archive.write_bytes(archive.read_bytes().replace(name.replace("\\", "/").encode(), name.encode()))
            with self.assertRaisesRegex(ImportFailure, "Unsafe archive member"):
                self.run_import(archive)
        archive = self.root / "link.cbz"
        entry = ZipInfo("page.jpg")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with ZipFile(archive, "w") as handle:
            handle.writestr(entry, "../outside")
        with self.assertRaisesRegex(ImportFailure, "Non-regular"):
            self.run_import(archive)
        archive = self.root / "duplicate.cbz"
        with ZipFile(archive, "w") as handle:
            handle.writestr("Page.jpg", b"one")
            handle.writestr("page.jpg", b"two")
        with self.assertRaisesRegex(ImportFailure, "Duplicate"):
            self.run_import(archive)
        with patch("pipeline.ingest.archive.MAX_IMAGE_BYTES", 100):
            with self.assertRaisesRegex(ImportFailure, "size limit.*page-1.jpg"):
                self.run_import(self.cbz)

    def test_corrupt_archive_pdf_and_named_pdf_page_failure(self) -> None:
        for suffix in [".cbz", ".pdf"]:
            path = self.root / f"broken{suffix}"
            path.write_bytes(b"invalid document")
            with self.assertRaisesRegex(ImportFailure, path.name):
                self.run_import(path)
        with patch("pipeline.ingest.pdf.PdfiumRasterizer.render", side_effect=RuntimeError("render failed")):
            with self.assertRaisesRegex(ImportFailure, "golden.pdf:page-1.*render failed"):
                self.run_import(self.pdf)
        archive = self.root / "crc.cbz"
        data = self.cbz.read_bytes()
        marker = golden_pages()[0].read_bytes()[:64]
        offset = data.index(marker)
        corrupted = bytearray(data)
        corrupted[offset + 10] ^= 1
        archive.write_bytes(corrupted)
        with self.assertRaisesRegex(ImportFailure, "chapter/page-1.jpg.*CRC"):
            self.run_import(archive)

    def test_natural_order_safe_ids_and_limits(self) -> None:
        self.assertEqual(sorted(["page10.jpg", "page2.jpg", "page1.jpg"], key=natural_key), ["page1.jpg", "page2.jpg", "page10.jpg"])
        for name in ["../escape", "CON", "C:drive", "a/b", ".hidden"]:
            with self.assertRaises(ImportFailure):
                ChapterStore(self.library, name, "chapter")
        with self.assertRaisesRegex(ImportFailure, "PDF resolution"):
            self.run_import(overrides={"pdf_dpi": 1000})
        with patch("pipeline.ingest.pages.MAX_PIXELS", 100):
            with self.assertRaisesRegex(ImportFailure, "page-1.jpg.*dimensions exceed"):
                self.run_import()


if __name__ == "__main__":
    unittest.main()
