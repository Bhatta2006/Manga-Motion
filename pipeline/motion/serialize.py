"""Geometry/timing validation in addition to the shared JSON Schema."""
import math
import json
import subprocess
from pathlib import Path
from pathlib import PurePosixPath

from pipeline.motion.solver import rect, contains


def validate_geometry(script):
    try:
        _geometry(script)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError(f'Malformed MotionScript geometry: {exc}') from exc


def _geometry(script):
    if script['version'] != 1: raise ValueError('Unsupported MotionScript version')
    ids = set()
    for page in script['pages']:
        size = page['size']
        if len(size) != 2 or any(type(x) is not int or x <= 0 for x in size):
            raise ValueError('Invalid page size')
        for item in [page] + page['panels']:
            if not item['id'] or item['id'] in ids: raise ValueError('Missing or duplicate ID')
            ids.add(item['id'])
        paths = [(page['image'], 'pages')]
        for panel in page['panels']:
            rect(panel['bbox'], size)
            for focus in panel['director']['focus']:
                rect(focus['bbox'], size)
                if 'char' in focus and focus['char'] not in script['characters']:
                    raise ValueError('Unknown focus character')
            last_time = camera_end = -1
            previous_camera = None
            count = 0
            for event in panel['timeline']:
                t = event['t']
                if type(t) not in (int, float) or not math.isfinite(t) or t < 0 or t < last_time:
                    raise ValueError('Invalid or unsorted timeline time')
                last_time = t
                if event['type'] in ('camera', 'line'):
                    dur = event['dur']
                    if type(dur) not in (int, float) or not math.isfinite(dur) or dur <= 0 or not math.isfinite(t + dur):
                        raise ValueError('Invalid duration')
                if event['type'] == 'camera':
                    count += 1
                    if (count == 1 and t != 0) or t < camera_end - 1e-7:
                        raise ValueError('Missing initial or overlapping camera event')
                    a, b = rect(event['from'], size), rect(event['to'], size)
                    if previous_camera is not None and any(abs(x-y) > 1e-7 for x,y in zip(a,previous_camera)):
                        raise ValueError('Discontinuous camera events')
                    for focus in panel['director']['focus']:
                        if focus['kind'] == 'bubble' and any(not contains(r, focus['bbox']) for r in (a,b)):
                            raise ValueError('Camera crops protected text')
                    camera_end, previous_camera = t + event['dur'], b
                elif event['type'] == 'sfx': paths.append((event['file'], 'sfx'))
                elif event['type'] == 'line':
                    paths.append((event['audio'], 'audio'))
                    if event['speaker'] not in script['characters']: raise ValueError('Unknown speaker')
            if not count: raise ValueError('Panel requires an initial camera event')
        for name, kind in paths:
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or len(p.parts) != 2 or p.parts[0] != kind:
                raise ValueError('Invalid asset path')


def validate_contract(script, project: Path | None = None) -> dict:
    """Validate with the reader's pinned AJV and shared semantic validator.

    A single Node process per chapter avoids another validator dependency and
    keeps Python/reader schema semantics identical. Missing Node fails before
    publication. Script contents go over stdin, never shell interpolation.
    """
    if script.get('version') == 1: validate_geometry(script)
    elif script.get('version') != 2: raise ValueError('Unsupported MotionScript version')
    project = project or Path(__file__).resolve().parents[2]
    payload = json.dumps(script, ensure_ascii=False, allow_nan=False)
    try:
        result = subprocess.run(['node', str(project / 'reader/tools/validate-contract.mjs')],
                                input=payload, text=True, encoding='utf-8', capture_output=True,
                                timeout=20, cwd=project, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f'Reader contract validation unavailable: {exc}') from exc
    if result.returncode != 0:
        raise ValueError(f'Reader contract rejected MotionScript: {result.stderr[:4000]}')
    return json.loads(result.stdout)
