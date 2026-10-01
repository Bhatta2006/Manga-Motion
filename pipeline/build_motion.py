"""Compile an analyzed imported chapter to MotionScript v1; no models or APIs."""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
import time
from pathlib import Path

from pipeline.cache import page_sha256
from pipeline.ingest import ImportFailure
from pipeline.ingest.hashes import object_hash
from pipeline.motion.compiler import CameraAdapter, VerifiedCameraCache
from pipeline.motion.serialize import validate_contract
from pipeline.runtime.scheduler import StageScheduler, StageExecutionError
from pipeline.store import ChapterStore, read_json, write_json


def build_motion(library: Path, series: str, chapter: str, runtime: Path, *, duration=2.0,
                 validator=validate_contract) -> tuple[dict, dict]:
    store = ChapterStore(library, series, chapter)
    if runtime.resolve().drive.upper() != 'D:' or not runtime.is_dir():
        raise ImportFailure('Dot-source scripts/enter-runtime.ps1; runtime must exist on D:')
    with store.lock():
        started = time.perf_counter()
        manifest = read_json(store.asset('import.json'))
        analysis = read_json(store.asset('analysis.json'))
        if not manifest or manifest.get('import_manifest_version') != 1 or not analysis or analysis.get('analysis_version') != 1:
            raise ImportFailure('Valid import.json and M1b analysis.json are required')
        if (analysis.get('chapter') != f'{series}/{chapter}' or analysis.get('input_sha256') != manifest['input_sha256']
                or analysis.get('direction') != manifest['settings']['direction']
                or analysis.get('source_language') != manifest['settings']['source_language']):
            raise ImportFailure('Analysis is stale for this import/settings; rerun M1b')
        if len(analysis['pages']) != len(manifest['pages']):
            raise ImportFailure('Analysis/import page count mismatch')
        input_snapshot = (object_hash(manifest), object_hash(analysis))
        records, unique = {}, {}
        for entry, page in zip(manifest['pages'], analysis['pages']):
            if any(page.get(k) != entry[k] for k in ('id', 'image', 'page_sha256', 'size')):
                raise ImportFailure(f'Analysis/import page mismatch: {entry["id"]}')
            asset = store.asset(page['image'])
            if not asset.is_file() or page_sha256(asset) != page['page_sha256']:
                raise ImportFailure(f'Imported art changed or missing: {entry["id"]}')
            record = {k: page[k] for k in ('size', 'panels', 'order', 'texts', 'review')}
            digest = page['page_sha256']
            if digest in records and records[digest] != record:
                raise ImportFailure('Repeated page hash has inconsistent analysis')
            records[digest], unique[digest] = record, asset
        if not unique:
            raise ImportFailure('Chapter contains no pages')
        dependencies = {h: {'analysis_sha256': object_hash(r)} for h, r in records.items()}
        scheduler = StageScheduler(runtime, VerifiedCameraCache(store.asset('cache/stages')))
        outputs, stage = scheduler.run_pages(CameraAdapter(records, duration), list(unique.values()),
                                            config={'duration': duration}, page_configs=dependencies)
        mapped = dict(zip(unique, outputs))
        script = {'version': 1, 'chapter': f'{series}/{chapter}', 'direction': analysis['direction'],
                  'characters': {}, 'pages': []}
        audits = []
        for page in analysis['pages']:
            compiled = mapped[page['page_sha256']]
            panels = copy.deepcopy(compiled['panels'])
            for panel in panels:
                panel['id'] = f'{page["id"]}_{panel["id"]}'
                for focus in panel['director']['focus']:
                    if 'ref' in focus: focus['ref'] = f'{page["id"]}_{focus["ref"]}'
            script['pages'].append({'id': page['id'], 'image': page['image'], 'size': compiled['size'], 'panels': panels})
            audits.append({'page': page['id'], 'page_sha256': page['page_sha256'],
                           'panels': compiled['audit'], 'review': compiled['review']})
            audits[-1]['readability'] = compiled['readability']
        validation_started = time.perf_counter()
        validation = validator(script)
        validation_seconds = time.perf_counter() - validation_started
        if input_snapshot != (object_hash(read_json(store.asset('import.json'))), object_hash(read_json(store.asset('analysis.json')))):
            raise ImportFailure('Import/analysis changed during compilation; retry with current inputs')
        for digest, asset in unique.items():
            if page_sha256(asset) != digest:
                raise ImportFailure(f'Source changed during compilation: {asset.name}')
        # No partial contract is published; previous valid output survives any failure above.
        write_json(store.asset('cache/camera-audit.json'), {'revision': CameraAdapter.revision, 'pages': audits})
        write_json(store.asset('motionscript.json'), script)
        metrics = {'stage': stage, 'validation': validation, 'validation_seconds': round(validation_seconds, 6),
                   'elapsed_seconds': round(time.perf_counter() - started, 6), 'pages_total': len(script['pages']),
                   'panels_total': sum(len(p['panels']) for p in script['pages']),
                   'motionscript_sha256': page_sha256(store.asset('motionscript.json')),
                   'timeline_seconds': sum(a['duration_seconds'] for p in audits for a in p['panels']),
                   'audio_seconds': 0, 'review_flags': sum(len(p['review']) for p in audits)}
        return script, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series', required=True)
    parser.add_argument('--chapter', required=True)
    parser.add_argument('--library', type=Path, default=Path(__file__).resolve().parents[1] / 'library')
    parser.add_argument('--run-label', default='current')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.run_label):
        parser.error('Use a simple local run label')
    try:
        _, metrics = build_motion(args.library, args.series, args.chapter, Path(os.environ.get('MANGAMOTION_RUNTIME', '')))
        write_json(Path(__file__).resolve().parents[1] / 'reports' / f'M1c-{args.run_label}.json', metrics)
        import json
        print(json.dumps(metrics, indent=2))
        return 0
    except (ImportFailure, ValueError, OSError, KeyError, TypeError, StageExecutionError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
