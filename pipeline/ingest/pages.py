"""Validate source rasters and expose the same bytes to the reader."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from PIL import Image

from pipeline.cache import cache_key, page_sha256
from pipeline.ingest import ImportFailure
from pipeline.store import ChapterStore, read_json, write_json

MAX_PIXELS = 40_000_000
FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tiff", "GIF": ".gif"}
REVISION = "ingest-raster-2-pillow-10.4.0"


def raster_info(path: Path) -> dict:
    with Image.open(path) as image:
        if image.width * image.height > MAX_PIXELS or min(image.size) < 1:
            raise ImportFailure(f"Image dimensions exceed limit: {image.size}")
        if image.format not in FORMATS or getattr(image, "n_frames", 1) != 1:
            raise ImportFailure(f"Unsupported format or multiple frames: {image.format}")
        if image.getexif().get(274, 1) != 1:
            raise ImportFailure("Non-identity EXIF orientation requires an explicit orientation policy")
        image.load()  # Fail on truncated images before committing any manifest.
        with image.convert("RGB") as rgb:
            pixels = hashlib.sha256(rgb.tobytes()).hexdigest()
        return {"size": list(image.size), "format": image.format, "pixel_sha256_rgb": pixels,
                "suffix": FORMATS[image.format]}


def validated_cached(store: ChapterStore, cache_path: Path) -> dict | None:
    record = read_json(cache_path)
    if record is None:
        return None
    try:
        asset = store.asset(record["image"])
        if page_sha256(asset) == record["page_sha256"]:
            return record
    except (KeyError, TypeError, ValueError, OSError):
        pass
    return None


def publish_raster(store: ChapterStore, source: Path, source_hash: str, settings: dict) -> tuple[dict, bool]:
    key = cache_key(source_hash, "ingest", REVISION, settings)
    cache_path = store.checked(store.chapter_root / "cache" / "ingest" / f"{key}.json")
    cached = validated_cached(store, cache_path)
    if cached is not None:
        return cached, True
    info = raster_info(source)
    # Browsers do not reliably decode TIFF. Preserve its original bytes and
    # publish only an exactly matching lossless PNG, without scaling/color edits.
    if info["format"] == "TIFF":
        parent = store.checked(store.chapter_root / "pages")
        parent.mkdir(parents=True, exist_ok=True)
        temp = parent / f".{uuid.uuid4().hex}.tmp"
        try:
            with Image.open(source) as image:
                if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
                    raise ImportFailure(f"TIFF mode requires an explicit conversion policy: {image.mode}")
                image.save(temp, format="PNG")
            converted = raster_info(temp)
            if converted["pixel_sha256_rgb"] != info["pixel_sha256_rgb"] or converted["size"] != info["size"]:
                raise ImportFailure("Lossless TIFF derivative did not match decoded source pixels")
            page_hash = page_sha256(temp)
            target = store.checked(parent / f"{page_hash}.png")
            temp.replace(target)
            fidelity = "pixel-identical-lossless-derivative"
        finally:
            temp.unlink(missing_ok=True)
    else:
        page_hash = source_hash
        target = store.checked(store.chapter_root / "pages" / f"{source_hash}{info['suffix']}")
        fidelity = "byte-identical-original"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file() or page_sha256(target) != page_hash:
        temp = target.with_name(f".{uuid.uuid4().hex}.tmp")
        try:
            shutil.copyfile(source, temp)
            if page_sha256(temp) != source_hash:
                raise ImportFailure("Source changed during page publication")
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
    record = {**info, "page_sha256": page_hash, "source_sha256": source_hash,
              "image": store.relative(target), "original": store.relative(source),
              "bytes": target.stat().st_size, "revision": REVISION, "cache_key": key,
              "fidelity": fidelity}
    write_json(cache_path, record)
    return record, False
