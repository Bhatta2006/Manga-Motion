"""Swappable CPU PDF rasterizer. No AI, resampling after render, or image generation."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Protocol

from pipeline.cache import cache_key, page_sha256
from pipeline.ingest import ImportFailure
from pipeline.ingest.hashes import object_hash
from pipeline.ingest.pages import MAX_PIXELS, raster_info, validated_cached
from pipeline.store import ChapterStore, write_json


class PdfRasterizer(Protocol):
    revision: str

    def open(self, source: Path) -> int: ...
    def render(self, index: int, destination: Path, dpi: int) -> None: ...
    def close(self) -> None: ...


class PdfiumRasterizer:
    revision = "pdfium-153.0.7999.0-pypdfium2-5.13.0-r1"

    def __init__(self) -> None:
        self.document = None

    def open(self, source: Path) -> int:
        import pypdfium2 as pdfium

        self.document = pdfium.PdfDocument(source)
        self.document.init_forms()
        return len(self.document)

    def render(self, index: int, destination: Path, dpi: int) -> None:
        page = self.document[index]
        bitmap = None
        image = None
        try:
            width, height = page.get_size()
            dimensions = [math.ceil(width * dpi / 72), math.ceil(height * dpi / 72)]
            if not all(math.isfinite(v) and v >= 1 for v in dimensions) or math.prod(dimensions) > MAX_PIXELS:
                raise ImportFailure(f"PDF raster dimensions exceed limit: {dimensions}")
            bitmap = page.render(scale=dpi / 72, fill_color=(255, 255, 255, 255))
            image = bitmap.to_pil()
            image.save(destination, format="PNG")
        finally:
            if image is not None:
                image.close()
            if bitmap is not None:
                bitmap.close()
            page.close()

    def close(self) -> None:
        if self.document is not None:
            self.document.close()
            self.document = None


def publish_pdf_page(store: ChapterStore, renderer: PdfRasterizer, source: Path,
                     source_hash: str, index: int, settings: dict) -> tuple[dict, bool]:
    key = cache_key(object_hash([source_hash, index]), "ingest-pdf", renderer.revision, settings)
    cache_path = store.checked(store.chapter_root / "cache" / "ingest-pdf" / f"{key}.json")
    cached = validated_cached(store, cache_path)
    if cached is not None:
        return cached, True
    parent = store.checked(store.chapter_root / "pages")
    parent.mkdir(parents=True, exist_ok=True)
    temp = parent / f".{uuid.uuid4().hex}.tmp"
    try:
        renderer.render(index, temp, settings["pdf_dpi"])
        info = raster_info(temp)
        page_hash = page_sha256(temp)
        destination = store.checked(parent / f"{page_hash}.png")
        if not destination.is_file() or page_sha256(destination) != page_hash:
            temp.replace(destination)
        record = {**info, "page_sha256": page_hash, "source_sha256": source_hash,
                  "source_page": index + 1, "image": store.relative(destination),
                  "original": store.relative(source), "bytes": destination.stat().st_size,
                  "revision": renderer.revision, "cache_key": key, "pdf_dpi": settings["pdf_dpi"],
                  "fidelity": "lossless-png-of-pdf-rasterization"}
        write_json(cache_path, record)
        return record, False
    finally:
        temp.unlink(missing_ok=True)
