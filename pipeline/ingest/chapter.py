"""Import one chapter, publishing a complete manifest only after all pages pass."""

from __future__ import annotations

import os
import re
import stat
import time
from pathlib import Path
from zipfile import ZipFile

from pipeline.cache import page_sha256
from pipeline.ingest import ImportFailure
from pipeline.ingest.archive import (IMAGE_SUFFIXES, MAX_IMAGE_BYTES, MAX_PAGES,
                                    MAX_SOURCE_BYTES, MAX_EXPANDED_BYTES, image_members, natural_key)
from pipeline.ingest.hashes import object_hash
from pipeline.ingest.pages import publish_raster
from pipeline.ingest.pdf import PdfiumRasterizer, PdfRasterizer, publish_pdf_page
from pipeline.runtime.scheduler import DeviceMemorySampler, _process_ram_mib
from pipeline.store import ChapterStore, read_json, write_json

DEFAULT_SETTINGS = {"direction": "rtl", "source_language": "en", "target_language": "en", "pdf_dpi": 144}


def is_link(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0)
                                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def validate_settings(settings: dict) -> dict:
    if set(settings) != set(DEFAULT_SETTINGS):
        raise ImportFailure("Unknown or missing per-series settings")
    if settings["direction"] not in {"rtl", "ltr"}:
        raise ImportFailure("Reading direction must be rtl or ltr")
    for key in ("source_language", "target_language"):
        if not isinstance(settings[key], str) or not re.fullmatch(r"[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*", settings[key]):
            raise ImportFailure(f"Invalid language in {key}: {settings[key]!r}")
    if type(settings["pdf_dpi"]) is not int or not 72 <= settings["pdf_dpi"] <= 300:
        raise ImportFailure("PDF resolution must be an integer from 72 to 300 dpi")
    return settings


def folder_pages(source: Path) -> tuple[list[Path], list[str]]:
    pages = []
    ignored = []
    entries = 0
    total_bytes = 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        for name in [*dirs, *files]:
            entries += 1
            path = Path(directory) / name
            if is_link(path) or not path.resolve().is_relative_to(source):
                raise ImportFailure(f"Linked folder entry is not allowed: {path.relative_to(source)}")
            if entries > MAX_PAGES * 4:
                raise ImportFailure("Folder has too many entries")
        for name in files:
            path = Path(directory) / name
            if path.suffix.lower() in IMAGE_SUFFIXES:
                length = path.stat().st_size
                total_bytes += length
                if length > MAX_IMAGE_BYTES or total_bytes > MAX_EXPANDED_BYTES:
                    raise ImportFailure(f"Folder size limit exceeded at: {path.relative_to(source)}")
                pages.append(path)
            else:
                ignored.append(path.relative_to(source).as_posix())
    if not pages or len(pages) > MAX_PAGES:
        raise ImportFailure(f"Folder requires 1..{MAX_PAGES} image pages; found {len(pages)}")
    return sorted(pages, key=lambda path: natural_key(path.relative_to(source).as_posix())), sorted(ignored)


def import_chapter(source: Path, library: Path, series: str, chapter: str,
                   overrides: dict | None = None, renderer: PdfRasterizer | None = None) -> tuple[dict, dict]:
    store = ChapterStore(library, series, chapter)
    if source.exists() and is_link(source):
        raise ImportFailure(f"Linked import source is not allowed: {source}")
    source = source.resolve()
    if source.is_dir() and store.root.is_relative_to(source):
        raise ImportFailure("Import folder cannot contain the destination library")
    with store.lock():
        saved = read_json(store.checked(store.series_root / "series.json")) or {}
        settings = validate_settings({**DEFAULT_SETTINGS, **saved.get("settings", {}), **(overrides or {})})
        started = time.perf_counter()
        sampler = DeviceMemorySampler()
        sampler.start()
        metrics = {"stage": "ingest", "heavy": False, "pages": [], "cache_hits": 0, "cache_misses": 0}
        records = []
        source_entries = []
        ignored = []
        source_container = None

        def record_page(label: str, start: float, record: dict, hit: bool) -> None:
            records.append({**record, "id": f"p{len(records) + 1:04d}", "source_name": label})
            source_entries.append({"name": label, "sha256": record["source_sha256"]})
            metrics["cache_hits" if hit else "cache_misses"] += 1
            metrics["pages"].append({"source_name": label, "page_sha256": record["page_sha256"],
                                     "cache_hit": hit, "seconds": round(time.perf_counter() - start, 6),
                                     "bytes": record["bytes"]})
            ram = _process_ram_mib()
            if ram is not None:
                sampler.process_ram_peak_mib = max(sampler.process_ram_peak_mib or ram, ram)

        def import_image(label: str, stream) -> None:
            start = time.perf_counter()
            try:
                original, value = store.copy_original(stream, ".image", MAX_IMAGE_BYTES)
                record, hit = publish_raster(store, original, value, settings)
                record_page(label, start, record, hit)
            except Exception as exc:
                raise ImportFailure(f"Page {label}: {exc}") from exc

        try:
            if source.is_dir():
                kind = "folder"
                pages, ignored = folder_pages(source)
                for page in pages:
                    label = page.relative_to(source).as_posix()
                    try:
                        with page.open("rb") as stream:
                            import_image(label, stream)
                        if page_sha256(page) != records[-1]["source_sha256"]:
                            raise ImportFailure(f"Page {label}: source changed during import")
                    except OSError as exc:
                        raise ImportFailure(f"Page {label}: {exc}") from exc
            elif source.is_file() and source.suffix.lower() in {".cbz", ".zip", ".pdf"}:
                kind = "pdf" if source.suffix.lower() == ".pdf" else "zip"
                with source.open("rb") as stream:
                    original, value = store.copy_original(stream, source.suffix.lower(), MAX_SOURCE_BYTES)
                source_container = {"file": store.relative(original), "sha256": value}
                if kind == "zip":
                    with ZipFile(original) as archive:
                        pages, ignored = image_members(archive)
                        for entry in pages:
                            try:
                                with archive.open(entry) as stream:
                                    import_image(entry.filename, stream)
                            except ImportFailure:
                                raise
                            except Exception as exc:
                                raise ImportFailure(f"Page {entry.filename}: {exc}") from exc
                else:
                    renderer = renderer or PdfiumRasterizer()
                    try:
                        count = renderer.open(original)
                        if not 1 <= count <= MAX_PAGES:
                            raise ImportFailure(f"PDF requires 1..{MAX_PAGES} pages; found {count}")
                        for index in range(count):
                            label = f"{source.name}:page-{index + 1}"
                            start = time.perf_counter()
                            try:
                                record, hit = publish_pdf_page(store, renderer, original, value, index, settings)
                                record_page(label, start, record, hit)
                            except Exception as exc:
                                raise ImportFailure(f"Page {label}: {exc}") from exc
                    finally:
                        renderer.close()
            else:
                raise ImportFailure(f"Expected a folder, CBZ/ZIP or PDF: {source}")
            # Ensure the input file did not change while being copied/processed.
            if source_container and page_sha256(source) != source_container["sha256"]:
                raise ImportFailure(f"Source changed during import: {source.name}")
            manifest = {"import_manifest_version": 1, "series": series, "chapter": chapter,
                        "source_kind": kind, "source_container": source_container, "settings": settings,
                        "input_sha256": object_hash({"pages": source_entries, "settings": settings}),
                        "pages": records, "ignored_files": ignored,
                        "order_policy": "PDF document order" if kind == "pdf" else "natural filename order",
                        "review_notes": [] if kind == "pdf" else ["Filename order is inferred; confirm it matches chapter reading order."]}
            write_json(store.checked(store.series_root / "series.json"), {"series": series, "settings": settings})
            write_json(store.checked(store.chapter_root / "import.json"), manifest)
        except Exception as exc:
            if isinstance(exc, ImportFailure):
                raise
            raise ImportFailure(f"Source {source.name}: {exc}") from exc
        finally:
            sampler.stop()
        metrics.update({"elapsed_seconds": round(time.perf_counter() - started, 6),
                        "pages_total": len(records), "device_vram_baseline_mib": sampler.baseline_mib,
                        "device_vram_peak_mib": sampler.peak_mib,
                        "process_ram_baseline_mib": sampler.process_ram_baseline_mib,
                        "process_ram_peak_mib": sampler.process_ram_peak_mib,
                        "process_lifetime_ram_peak_mib": _process_ram_mib(peak=True),
                        "current_page_bytes": sum(r["bytes"] for r in records),
                        "chapter_disk_bytes": sum(p.stat().st_size for p in store.chapter_root.rglob("*") if p.is_file())})
        return manifest, metrics
