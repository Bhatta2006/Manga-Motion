import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.build_motion import build_motion
from pipeline.store import read_json,write_json
from pipeline.cache import page_sha256
from pipeline.motion.solver import contains,interpolate
root=Path(__file__).resolve().parents[1];chapter=root/'library/golden-m1d/chapter'
script,metrics=build_motion(root/'library','golden-m1d','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
for page in script['pages']:
 for panel in page['panels']:
  for event in panel['timeline']:
   if event['type']!='camera':continue
   for i in range(101):
    pose=interpolate(event['from'],event['to'],i/100)
    assert 0<=pose[0]<pose[2]<=page['size'][0] and 0<=pose[1]<pose[3]<=page['size'][1]
    assert all(contains(pose,f['bbox']) for f in panel['director']['focus'] if f['kind']=='bubble')
assert all(page_sha256(chapter/p['image'])==p['page_sha256'] for p in read_json(chapter/'analysis.json')['pages'])
audit=read_json(chapter/'cache/camera-audit.json');items=[a for p in audit['pages'] for a in p['panels']]
result={'metrics':metrics,'source_hashes_unchanged':True,'pose_samples_per_segment':101,
        'constraint_violations':sum(a['constraint_violations'] for a in items),
        'maxima':{k:max(a[k] for a in items) for k in ('max_relative_scale','max_zoom_rate_per_second','max_pan_panel_widths_per_second')},
        'focus_fallbacks':sum('focus_fallback' in a for a in items),
        'small_text_boxes':{str(viewport):sum(len(p['small_text_boxes']) for page in audit['pages'] for p in page['readability'] if p['viewport']==viewport) for viewport in ([390,600],[1280,700])}}
write_json(root/'reports/M3b-golden.json',result);print(json.dumps(result,indent=2))
