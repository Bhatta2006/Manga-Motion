"""CLI for M1a; downstream detection/rendering is a separate milestone."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pipeline.ingest import ImportFailure
from pipeline.ingest.chapter import import_chapter
from pipeline.store import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--series", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--library", type=Path, default=Path(__file__).resolve().parents[1] / "library")
    parser.add_argument("--direction", choices=["rtl", "ltr"])
    parser.add_argument("--source-language")
    parser.add_argument("--target-language")
    parser.add_argument("--pdf-dpi", type=int)
    parser.add_argument("--metrics", type=Path)
    args = parser.parse_args()
    try:
        if args.metrics is not None and os.name == "nt" and args.metrics.resolve().drive.upper() != "D:":
            raise ImportFailure("Metrics writes must stay on D:")
        overrides = {key: getattr(args, key) for key in ("direction", "source_language", "target_language", "pdf_dpi")
                     if getattr(args, key) is not None}
        manifest, metrics = import_chapter(args.source, args.library, args.series, args.chapter, overrides)
        if args.metrics is not None:
            write_json(args.metrics.resolve(), metrics)
        print(json.dumps({"manifest": str(args.library / args.series / args.chapter / "import.json"),
                          "pages": len(manifest["pages"]), "metrics": metrics}, indent=2))
        return 0
    except ImportFailure as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
