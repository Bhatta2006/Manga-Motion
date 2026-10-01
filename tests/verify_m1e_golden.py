"""Actual five-page pacing, source integrity, cache/rate and private label evidence."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.build_motion import build_motion
from pipeline.cache import page_sha256
from pipeline.motion.serialize import validate_contract
from pipeline.store import read_json, write_json, ChapterStore
from pipeline.api.chapters import playback_info

root=Path(__file__).resolve().parents[1]
store=ChapterStore(root/'library','golden-m1d','chapter')
analysis=read_json(store.asset('analysis.json'))
reference=read_json(root/'library/golden-m1b/reference.json')
categories={r['category'] for p in reference['pages'] for r in p['ocr']}
assert categories <= {'dialogue','caption','sfx','watermark','translator_note','nonverbal','sign'}, categories
labels={'input_sha256':analysis['input_sha256'], 'method':reference['method'],
        'pages':{p['page_sha256']:{f'text_{r["text_index"]:03}':r['category'] for r in p['ocr']} for p in reference['pages']}}
write_json(store.asset('pacing-labels.json'),labels)
sources={p['image']:page_sha256(store.asset(p['image'])) for p in analysis['pages']}
runs={}
for label,rate in [('first',240),('warm',240),('slow',160),('fast',320),('restore',240)]:
    script,metrics=build_motion(root/'library',store.series,store.chapter,Path(os.environ['MANGAMOTION_RUNTIME']),reading_wpm=rate,persist_rate=True)
    validate_contract(script)
    audit=read_json(store.asset('cache/camera-audit.json'))
    timings=[p['duration_seconds'] for page in audit['pages'] for p in page['panels']]
    words=[p['reading']['words'] for page in audit['pages'] for p in page['panels']]
    assert len(timings)==25
    runs[label]={'metrics':metrics,'timings':timings,'words':words,
                 'unknown_words':sum(p['reading']['estimated_unknown_words'] for page in audit['pages'] for p in page['panels'])}
assert runs['warm']['metrics']['stage']['cache_hits']==5
assert runs['slow']['metrics']['motionscript_sha256']!=runs['fast']['metrics']['motionscript_sha256']
assert all(a>=b for a,b in zip(runs['slow']['timings'],runs['fast']['timings']))
assert max(runs['first']['timings'])>min(runs['first']['timings'])
assert sources=={p['image']:page_sha256(store.asset(p['image'])) for p in analysis['pages']}
assert playback_info(store)['reading_wpm']==240
write_json(root/'reports/M1e-golden.json',runs)
print(json.dumps({'source_hashes_unchanged':True,'pages':5,'panels':25,'categories':sorted(categories),
                  'min_dwell':min(runs['first']['timings']),'max_dwell':max(runs['first']['timings']),
                  'words':sum(runs['first']['words']),'unknown_words':runs['first']['unknown_words'],
                  'runs':{k:v['metrics'] for k,v in runs.items()}},indent=2))
