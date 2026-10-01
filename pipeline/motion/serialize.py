"""Geometry/timing validation in addition to the shared JSON Schema."""
import math
from pathlib import PurePosixPath


def validate_geometry(script):
    if script['version'] != 1: raise ValueError('Unsupported MotionScript version')
    ids = set()
    for page in script['pages']:
        w,h = page['size']
        for item in [page]+page['panels']:
            if item['id'] in ids: raise ValueError('Duplicate ID')
            ids.add(item['id'])
        paths = [page['image']]
        for panel in page['panels']:
            rects = [panel['bbox']]+[f['bbox'] for f in panel['director']['focus']]
            for event in panel['timeline']:
                if not math.isfinite(event['t']) or event['t']<0: raise ValueError('Invalid time')
                if event['type']=='camera':
                    rects.extend([event['from'],event['to']])
                    if event['dur']<=0: raise ValueError('Invalid duration')
                    for bubble in [f['bbox'] for f in panel['director']['focus'] if f['kind']=='bubble']:
                        for rect in (event['from'],event['to']):
                            if not (rect[0]<=bubble[0] and rect[1]<=bubble[1] and rect[2]>=bubble[2] and rect[3]>=bubble[3]):
                                raise ValueError('Camera crops protected text')
                elif event['type']=='sfx': paths.append(event['file'])
                elif event['type']=='line':
                    paths.append(event['audio'])
                    if event['speaker'] not in script['characters']: raise ValueError('Unknown speaker')
            for b in rects:
                if not all(math.isfinite(x) for x in b) or not (0<=b[0]<b[2]<=w and 0<=b[1]<b[3]<=h):
                    raise ValueError(f'Invalid page rectangle: {b}')
        for name in paths:
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or len(p.parts)!=2 or p.parts[0] not in ('pages','audio','sfx'):
                raise ValueError('Invalid asset path')
