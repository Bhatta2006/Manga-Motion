from pipeline.store import read_json


def series_notes(store):
    path=store.checked(store.series_root/'director-settings.json')
    settings=read_json(path)
    if path.exists() and settings is None:raise ValueError('Director settings are damaged')
    settings=settings or {}
    if set(settings)-{'notes'}:raise ValueError('Unknown director settings')
    notes=settings.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000:raise ValueError('Director notes must be text up to 2000 characters')
    return notes
