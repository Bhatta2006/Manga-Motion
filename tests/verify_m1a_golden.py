"""Measure real-page import in fresh processes, with private fixtures on D."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest_fixtures import ROOT, build_fixtures, golden_pages
from pipeline.cache import page_sha256


def main() -> None:
    fixture_root = ROOT / "library/fixtures/m1a"
    sources = build_fixtures(fixture_root)
    series = f"m1a-benchmark-{uuid.uuid4().hex[:8]}"
    evidence = {"series": series, "sources": [], "runs": []}
    original_hashes = [page_sha256(p) for p in golden_pages()]
    for kind, source in zip(["folder", "cbz", "pdf"], sources):
        for state in ["cold", "warm"]:
            result = subprocess.run([sys.executable, "-m", "pipeline.import_chapter", str(source),
                                     "--series", series, "--chapter", kind], cwd=ROOT,
                                    capture_output=True, text=True, encoding="utf-8", check=True)
            record = json.loads(result.stdout)
            manifest_path = Path(record["manifest"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            hashes = [p["page_sha256"] for p in manifest["pages"]]
            if kind != "pdf":
                assert hashes == original_hashes
            assert len(hashes) == 5
            assert record["metrics"]["cache_hits"] == (5 if state == "warm" else 0)
            evidence["runs"].append({"kind": kind, "state": state, **record})
        evidence["sources"].append({"kind": kind, "path": str(source), "page_hashes": hashes})
    assert [page_sha256(p) for p in golden_pages()] == original_hashes
    evidence["original_hashes_unchanged"] = True
    destination = ROOT / "reports/M1a-golden-metrics.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    for run in evidence["runs"]:
        m = run["metrics"]
        print(json.dumps({"kind": run["kind"], "state": run["state"],
                          "seconds": m["elapsed_seconds"], "hits": m["cache_hits"],
                          "page_seconds": [p["seconds"] for p in m["pages"]],
                          "gpu_peak_mib": m["device_vram_peak_mib"],
                          "ram_lifetime_peak_mib": m["process_lifetime_ram_peak_mib"],
                          "chapter_disk_bytes": m["chapter_disk_bytes"]}))
    print(f"Private evidence: {destination}")


if __name__ == "__main__":
    main()
