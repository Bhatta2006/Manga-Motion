"""M1b page metadata to restrained v1 camera events and separate audit data."""

from __future__ import annotations

from pipeline.cache import JsonStageCache, page_sha256
from pipeline.ingest.hashes import object_hash
from pipeline.motion.rules import panel_rule, safe_transition
from pipeline.motion.solver import rect, solve_camera
from pipeline.motion.timing import timeline_duration

REVISION = 'camera-m1c-4'


def compile_page(record: dict, *, duration=2.0) -> dict:
    size = record['size']
    panels = record['panels']
    ids = [p['id'] for p in panels]
    order = record['order']['panel_ids']
    if not ids or len(set(ids)) != len(ids) or len(order) != len(ids) or set(order) != set(ids):
        raise ValueError('Panel order must be a complete unique permutation')
    text_ids = [t['id'] for t in record['texts']]
    if len(text_ids) != len(set(text_ids)):
        raise ValueError('Duplicate text ID')
    for text in record['texts']:
        rect(text['bbox'], size)
        if text['panel_id'] is not None and text['panel_id'] not in ids:
            raise ValueError('Text refers to an unknown panel')
    lookup = {p['id']: p for p in panels}
    result, audits = [], []
    for index, panel_id in enumerate(order):
        panel = lookup[panel_id]
        texts = [t for t in record['texts'] if t['panel_id'] == panel_id]
        recipe, shot = panel_rule(index, bool(texts), len(panels) == 1)
        # Ambiguous order keeps explicit provisional order but disables intra-panel motion.
        if record['order']['needs_review'] or panel.get('origin') != 'detected':
            recipe = 'hold'
        event, audit = solve_camera(panel['bbox'], [t['bbox'] for t in texts], size,
                                    recipe=recipe, duration=duration)
        audit.update({'panel_id': panel_id, 'duration_seconds': timeline_duration([event]),
                      'protected_texts': len(texts)})
        focus = [{'kind': 'region', 'ref': 'camera-target', 'bbox': audit['protected']}]
        focus += [{'kind': 'bubble', 'ref': t['id'], 'bbox': t['bbox']} for t in texts]
        # No claims about dialogue, mood or identity from a binary essential flag.
        result.append({'id': panel_id, 'bbox': panel['bbox'],
                       'director': {'beat': 'quiet', 'shot': shot, 'energy': .1, 'mood': [],
                                    'time_skip': False, 'focus': focus},
                       'timeline': [event], 'transition_out': {'type': 'glide', 'dur': .32},
                       'confidence': {'panel': None, 'ocr': None, 'speaker': None}})
        audits.append(audit)
    for index, panel in enumerate(result):
        if index + 1 < len(result):
            widths = [p['bbox'][2]-p['bbox'][0] for p in (panel,result[index+1])]
            panel['transition_out'], audits[index]['transition'] = safe_transition(panel['timeline'][0], result[index+1]['timeline'][0], panel_widths=widths)
        else:
            panel['transition_out'] = {'type':'fade','dur':.2}
            audits[index]['transition'] = {'reason':'page_boundary','glide_allowed':False}
    # Box height is an inspectable proxy, not a claim about actual glyph size.
    readability = []
    for viewport in ((390,600),(1280,700)):
        small = []
        for panel in result:
            event = panel['timeline'][0]
            scale = min(min(viewport[0]/(r[2]-r[0]),viewport[1]/(r[3]-r[1])) for r in (event['from'],event['to']))
            for focus in panel['director']['focus']:
                if focus['kind']=='bubble' and (focus['bbox'][3]-focus['bbox'][1])*scale < 24:
                    small.append({'panel_id':panel['id'],'text_id':focus['ref'],
                                  'box_height_css_px':(focus['bbox'][3]-focus['bbox'][1])*scale})
        readability.append({'viewport':list(viewport),'minimum_box_height_css_px':24,'small_text_boxes':small,
                            'glyph_size_status':'unmeasured; text-box height is not font size'})
    output = {'size': size, 'panels': result, 'audit': audits, 'review': record['review'], 'readability':readability}
    return {**output, 'content_sha256': object_hash(output)}


class VerifiedCameraCache(JsonStageCache):
    """Damaged but parseable camera artifacts must be recomputed, not played."""
    def read(self, stage, key):
        output = super().read(stage, key)
        if output is None:
            return None
        try:
            payload = {k: output[k] for k in ('size', 'panels', 'audit', 'review', 'readability')}
            return output if output.get('content_sha256') == object_hash(payload) else None
        except (KeyError, TypeError, ValueError):
            return None


class CameraAdapter:
    stage_name = 'camera-solver'
    revision = REVISION
    heavy = False

    def __init__(self, records, duration=2.0):
        self.records, self.duration = records, duration

    def load(self): pass
    def unload(self): pass

    def run_page(self, page):
        return compile_page(self.records[page_sha256(page)], duration=self.duration)
