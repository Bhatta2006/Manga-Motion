"""Immutable playback snapshots and explicitly allowlisted source assets."""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import HTTPException
from starlette.responses import Response

from pipeline.cache import page_sha256
from pipeline.ingest.hashes import object_hash
from pipeline.motion.serialize import validate_contract
from pipeline.store import ChapterStore, read_json, write_json


def asset_paths(script):
    paths = {page['image'] for page in script['pages']}
    for scene in script.get('scenes',{}).values():
        paths.update(b['file'] for b in scene['beds'])
    for page in script['pages']:
        for panel in page['panels']:
            paths.update(layer['mask'] for layer in panel.get('layers',[]))
            for event in panel['timeline']:
                if event['type'] == 'sfx': paths.add(event['file'])
                if event['type'] == 'line': paths.add(event['audio'])
    return paths


def checked_asset(store, relative):
    if not re.fullmatch(r'(pages|sfx|audio|music|ambience|layers)/[A-Za-z0-9][A-Za-z0-9_.-]*', relative):
        raise ValueError('Asset path is outside the playback allowlist')
    return store.asset(relative)


def snapshot(store: ChapterStore, script=None):
    script = script if script is not None else read_json(store.asset('motionscript.json'))
    if script is None:
        raise ValueError('Chapter is not ready to read')
    if script.get('chapter') != f'{store.series}/{store.chapter}':
        raise ValueError('Playback belongs to a different chapter')
    digest = object_hash(script)
    path = store.asset(f'cache/playback/{digest}.json')
    existing = read_json(path)
    if existing and object_hash(existing.get('script')) == digest and existing.get('checksum') == object_hash({'script':existing['script'],'assets':existing.get('assets')}):
        return digest, existing
    validate_contract(script)
    assets = {}
    for relative in asset_paths(script):
        asset = checked_asset(store, relative)
        value = page_sha256(asset)
        if relative.startswith('pages/') and re.fullmatch(r'[a-f0-9]{64}', asset.stem) and asset.stem != value:
            raise ValueError(f'Art integrity check failed: {relative}')
        assets[relative] = value
    for scene in script.get('scenes',{}).values():
        for bed in scene['beds']:
            if assets[bed['file']]!=bed['sha256']:raise ValueError('Bed asset hash mismatch')
            import wave
            try:
                with wave.open(str(checked_asset(store,bed['file']))) as audio:
                    actual=audio.getnframes()/audio.getframerate();tolerance=1/audio.getframerate()
            except (wave.Error,EOFError) as exc:raise ValueError('Bed must be verified PCM WAV in this provider') from exc
            if abs(actual-bed['duration'])>tolerance or bed['loop'][1]>actual+tolerance:raise ValueError('Bed duration/loop differs from actual audio')
    for page in script['pages']:
        for panel in page['panels']:
            for layer in panel.get('layers',[]):
                if assets[layer['mask']]!=layer['safety']['mask_sha256'] or assets[page['image']]!=layer['safety']['source_sha256']:
                    raise ValueError('Layer source/mask hash mismatch')
    record = {'script': script, 'assets': assets}
    record['checksum'] = object_hash(record)
    write_json(path, record)
    return digest, record


def read_snapshot(store, digest):
    if not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise HTTPException(404, 'Unknown playback')
    record = read_json(store.asset(f'cache/playback/{digest}.json'))
    if not record or object_hash(record.get('script')) != digest or record.get('checksum') != object_hash({'script':record['script'],'assets':record.get('assets')}) or set(record.get('assets', {})) != asset_paths(record['script']):
        raise HTTPException(409, 'Playback snapshot is missing or damaged; reopen the chapter')
    return record


def playback_info(store, *, stream=None):
    digest, record = snapshot(store,stream['script'] if stream else None)
    base = f'/api/chapters/{store.series}/{store.chapter}/playback/{digest}'
    script = record['script']
    audit = read_json(store.asset('cache/camera-audit.json')) or {}
    rate = stream['reading_wpm'] if stream else audit.get('reading_wpm') if audit.get('script_hash') == digest else None
    return {'snapshot': digest, 'script_url': base+'/motionscript.json', 'asset_base': base+'/assets/',
            'pages': len(script['pages']), 'panels': sum(len(p['panels']) for p in script['pages']),
            'reading_wpm':rate,'partial':bool(stream),'total_pages':stream['total_pages'] if stream else len(script['pages'])}


def asset_response(store, digest, relative):
    record = read_snapshot(store, digest)
    if relative not in record['assets']:
        raise HTTPException(404, 'Asset is not part of this playback')
    asset = checked_asset(store, relative)
    # Serve the bytes we checked, avoiding a check/stream race during external edits.
    import hashlib
    content = asset.read_bytes()
    if hashlib.sha256(content).hexdigest() != record['assets'][relative]:
        raise HTTPException(409, 'Asset integrity check failed; restore the original and retry')
    return Response(content, media_type=mimetypes.guess_type(asset.name)[0] or 'application/octet-stream',
                    headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def library_entries(root: Path, jobs):
    latest = {}
    for job in jobs:
        latest.setdefault((job['series'],job['chapter']), job)
    keys = set(latest)
    for series in root.iterdir():
        if not series.is_dir() or not series.resolve().is_relative_to(root): continue
        for chapter in series.iterdir():
            if chapter.is_dir() and ((chapter/'import.json').is_file() or (chapter/'motionscript.json').is_file()):
                keys.add((series.name,chapter.name))
    entries = []
    for series, chapter in sorted(keys):
        try:
            store = ChapterStore(root, series, chapter)
            manifest = read_json(store.asset('import.json')) or {}
            script = read_json(store.asset('motionscript.json')) or {}
            analysis = read_json(store.asset('analysis.json')) or {}
            job = latest.get((series,chapter))
            if job: job = {k:job[k] for k in ('id','series','chapter','status','phase','progress','attempts','error')}
            pages = script.get('pages', [])
            from pipeline.streaming import streaming_record
            stream = streaming_record(store,job['id']) if job and job['status']!='completed' else None
            if stream:pages=stream['script']['pages']
            directed=read_json(store.asset('cache/director.json')) or {}
            semantic_review=stream.get('semantic_review_pages',0) if stream else sum(bool(p.get('semantics',{}).get('needs_review')) for p in directed.get('pages',[]))
            sounds=read_json(store.asset('cache/scene-sfx.json')) or {}
            sound_review=sum(len(p.get('review',[]))+sum(bool(e.get('audit',{}).get('needs_review')) for e in p.get('events',[])) for p in sounds.get('pages',[]))
            music=read_json(store.asset('cache/music-scenes.json')) or {}
            music_review=sum(len(p.get('review',[])) for p in music.get('pages',[]))
            entries.append({'series':series, 'chapter':chapter, 'pages':len(pages) or len(manifest.get('pages', [])),
                            'playable':bool(pages), 'status':job['status'] if job else ('completed' if pages else 'imported'),
                            'job':job,'partial':bool(stream),'ready_pages':len(pages),
                            'total_pages':len(manifest.get('pages', [])) or len(pages),
                            'semantic_review_pages':semantic_review,
                            'review_flags':sum(len(p.get('review', [])) for p in analysis.get('pages', []))+semantic_review+sound_review+music_review})
        except (ValueError, OSError, TypeError, KeyError):
            continue
    return entries
