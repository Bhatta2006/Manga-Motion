"""Local pipeline configuration; playback remains self-contained MotionScript v1."""
from pipeline.store import read_json
from pipeline.motion.timing import reading_rate, READING_KINDS, EXCLUDED_KINDS


def configured_rate(store):
    path = store.checked(store.series_root/'pacing.json')
    settings = read_json(path)
    if path.exists() and settings is None:
        raise ValueError('Reading settings are damaged')
    return reading_rate((settings or {}).get('reading_wpm', 240))


def pacing_labels(store, analysis):
    path = store.asset('pacing-labels.json')
    labels = read_json(path)
    if path.exists() and labels is None:
        raise ValueError('Pacing labels are damaged')
    if labels is None:
        return {}
    if labels.get('input_sha256') != analysis['input_sha256']:
        raise ValueError('Pacing labels belong to an older import')
    pages = {p['page_sha256']:{t['id'] for t in p['texts']} for p in analysis['pages']}
    values = labels.get('pages')
    if not isinstance(values, dict):
        raise ValueError('Pacing labels require a page-hash map')
    for digest, texts in values.items():
        if digest not in pages or not isinstance(texts, dict):
            raise ValueError('Unknown pacing label page')
        for text_id, kind in texts.items():
            if text_id not in pages[digest] or kind not in READING_KINDS | EXCLUDED_KINDS | {'unknown'}:
                raise ValueError('Unknown pacing label text/kind')
    return values
