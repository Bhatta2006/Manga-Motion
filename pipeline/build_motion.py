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
from pipeline.motion.compiler import CameraAdapter, VerifiedCameraCache, camera_record
from pipeline.motion.pacing import configured_rate, pacing_labels
from pipeline.motion.timing import reading_rate, PACING_REVISION
from pipeline.director.settings import series_notes
from pipeline.audio.scene import prepare_pages as prepare_sfx,append_events
from pipeline.motion.serialize import validate_contract
from pipeline.runtime.scheduler import StageScheduler, StageExecutionError
from pipeline.store import ChapterStore, read_json, write_json


def build_motion(library: Path, series: str, chapter: str, runtime: Path, *, duration=2.0,
                 validator=validate_contract, progress=None, reading_wpm=None, persist_rate=False) -> tuple[dict, dict]:
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
        rate = configured_rate(store) if reading_wpm is None else reading_rate(reading_wpm)
        labels = pacing_labels(store, analysis)
        directed=read_json(store.asset('cache/director.json'))
        if directed and directed.get('analysis_sha256')!=object_hash(analysis):raise ImportFailure('Director is stale for this analysis; rerun processing')
        if directed and directed.get('notes_sha256') not in (None,object_hash(series_notes(store))):raise ImportFailure('Director notes changed; rerun processing')
        directed_pages={p['page_sha256']:p for p in (directed or {}).get('pages',[])}
        if directed is not None and set(directed_pages)!={p['page_sha256'] for p in analysis['pages']}:
            raise ImportFailure('Director page coverage is incomplete; rerun processing')
        input_snapshot = (object_hash(manifest), object_hash(analysis), object_hash(labels),object_hash(directed))
        records, unique = {}, {}
        for entry, page in zip(manifest['pages'], analysis['pages']):
            if any(page.get(k) != entry[k] for k in ('id', 'image', 'page_sha256', 'size')):
                raise ImportFailure(f'Analysis/import page mismatch: {entry["id"]}')
            asset = store.asset(page['image'])
            if not asset.is_file() or page_sha256(asset) != page['page_sha256']:
                raise ImportFailure(f'Imported art changed or missing: {entry["id"]}')
            digest = page['page_sha256']
            record = camera_record({**page,**directed_pages.get(digest,{})},labels.get(digest,{}))
            if digest in records and records[digest] != record:
                raise ImportFailure('Repeated page hash has inconsistent analysis')
            records[digest], unique[digest] = record, asset
        if not unique:
            raise ImportFailure('Chapter contains no pages')
        dependencies = {h: {'analysis_sha256': object_hash(r)} for h, r in records.items()}
        scheduler = StageScheduler(runtime, VerifiedCameraCache(store.asset('cache/stages')))
        outputs, stage = scheduler.run_pages(CameraAdapter(records, duration, rate), list(unique.values()),
                                            config={'duration': duration, 'reading_wpm':rate, 'pacing_revision':PACING_REVISION}, page_configs=dependencies, progress=progress)
        mapped = dict(zip(unique, outputs))
        sounds,sfx_stage=prepare_sfx(store,records,list(unique.values()),runtime,progress)
        sound_map=dict(zip(unique,sounds))
        script = {'version': 1, 'chapter': f'{series}/{chapter}', 'direction': analysis['direction'],
                  'characters': {}, 'pages': []}
        audits = []
        for page in analysis['pages']:
            compiled = mapped[page['page_sha256']]
            panels = copy.deepcopy(compiled['panels'])
            append_events(panels,sound_map[page['page_sha256']])
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
        if input_snapshot != (object_hash(read_json(store.asset('import.json'))), object_hash(read_json(store.asset('analysis.json'))), object_hash(pacing_labels(store, analysis)),object_hash(read_json(store.asset('cache/director.json')))):
            raise ImportFailure('Import/analysis changed during compilation; retry with current inputs')
        for digest, asset in unique.items():
            if page_sha256(asset) != digest:
                raise ImportFailure(f'Source changed during compilation: {asset.name}')
        # No partial contract is published; previous valid output survives any failure above.
        write_json(store.asset('cache/camera-audit.json'), {'revision': CameraAdapter.revision, 'pages': audits,
                   'reading_wpm':rate, 'script_hash':object_hash(script)})
        write_json(store.asset('cache/scene-sfx.json'),{'revision':sfx_stage['revision'],'pages':[{'page_sha256':digest,**value} for digest,value in sound_map.items()]})
        from pipeline.audio.sfx_map import CATEGORIES
        from pipeline.audio.sfx_library import RATE,REVISION as sound_recipe
        write_json(store.checked(store.root/'sfx/manifest.json'),{'recipe':sound_recipe,'sample_rate':RATE,'categories':sorted(CATEGORIES),
                   'source':'MangaMotion owned procedural recipes; no third-party recordings','license':'Project-generated; personal use authorized',
                   'assets_location':'Each chapter sfx/; exact file hashes and provenance in its cache/scene-sfx.json'})
        write_json(store.asset('motionscript.json'), script)
        if persist_rate:
            write_json(store.checked(store.series_root/'pacing.json'), {'reading_wpm':rate})
        metrics = {'stage': stage,'sfx_stage':sfx_stage, 'validation': validation, 'validation_seconds': round(validation_seconds, 6),
                   'elapsed_seconds': round(time.perf_counter() - started, 6), 'pages_total': len(script['pages']),
                   'panels_total': sum(len(p['panels']) for p in script['pages']),
                   'motionscript_sha256': page_sha256(store.asset('motionscript.json')),
                   'timeline_seconds': sum(a['duration_seconds'] for p in audits for a in p['panels']),
                   'audio_seconds': sum(a['duration'] for v in sound_map.values() for a in v['assets']),
                   'sfx_events':sum(len(v['events']) for v in sound_map.values()),
                   'review_flags': sum(len(p['review']) for p in audits)+sum(len(v['review']) for v in sound_map.values())}
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
