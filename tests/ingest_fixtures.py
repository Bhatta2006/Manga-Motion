"""Private format fixtures built from the user's original five JPEG pages.

PDF fixture embeds each original JPEG stream directly, without re-encoding.
At 144 dpi each PDF page has exactly the source image's dimensions.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from pipeline.cache import page_sha256

ROOT = Path(__file__).resolve().parents[1]


def golden_pages() -> list[Path]:
    inventory = json.loads((ROOT / "reports/M0a-cold-metrics.json").read_text(encoding="utf-8"))
    pages = []
    for record in inventory["pages"]:
        path = Path(record["page"])
        if page_sha256(path) != record["page_sha256"]:
            raise AssertionError(f"Golden source changed: {path.name}")
        pages.append(path)
    if len(pages) != 5:
        raise AssertionError("Expected the five real user pages")
    return pages


def write_pdf(path: Path, pages: list[Path]) -> None:
    objects: list[bytes] = [b"", b""]
    page_ids = []
    for source in pages:
        with Image.open(source) as image:
            width, height = image.size
            if image.format != "JPEG" or image.mode not in {"RGB", "L"}:
                raise AssertionError("Fixture expects RGB or grayscale JPEG originals")
            color_space = "DeviceRGB" if image.mode == "RGB" else "DeviceGray"
        page_id = len(objects) + 1
        image_id = page_id + 1
        content_id = page_id + 2
        page_ids.append(page_id)
        pw, ph = width / 2, height / 2
        content = f"q {pw} 0 0 {ph} 0 0 cm /Im0 Do Q".encode("ascii")
        data = source.read_bytes()
        objects += [
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw} {ph}] /Resources << /XObject << /Im0 {image_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii"),
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /{color_space} /BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n".encode("ascii") + data + b"\nendstream",
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
        ]
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{value} 0 R" for value in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        result += f"{offset:010d} 00000 n \n".encode("ascii")
    result += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    path.write_bytes(result)


def build_fixtures(root: Path) -> tuple[Path, Path, Path]:
    pages = golden_pages()
    folder = root / "folder"
    folder.mkdir(parents=True, exist_ok=True)
    cbz = root / "golden.cbz"
    pdf = root / "golden.pdf"
    with ZipFile(cbz, "w", compression=ZIP_STORED) as archive:
        for index, source in enumerate(pages, start=1):
            name = f"page-{index}.jpg"
            shutil.copyfile(source, folder / name)
            archive.write(source, f"chapter/{name}")
        archive.writestr("notes.txt", "Private five-page format fixture, not a continuous chapter.")
    write_pdf(pdf, pages)
    return folder, cbz, pdf
