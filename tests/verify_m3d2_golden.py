import json,os,sys,wave,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.audio.prepare_music import prepare_chapter
from pipeline.store import read_json,write_json
from pipeline.cache import page_sha256
from pipeline.ingest.hashes import object_hash
root=Path(__file__).resolve().parents[1];chapter=root/'library/golden-m1d/chapter'
before=read_json(chapter/'motionscript.json');source={p['image']:page_sha256(chapter/p['image']) for p in before['pages']}
script,cold=prepare_chapter(root/'library','golden-m1d','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
_,warm=prepare_chapter(root/'library','golden-m1d','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
assert warm['stage']['cache_hits']==5
assert read_json(chapter/'motionscript.json')==before
assert source=={p['image']:page_sha256(chapter/p['image']) for p in before['pages']}
flattened=copy.deepcopy(script);flattened['version']=before['version'];flattened.pop('scenes')
for p in flattened['pages']:
 for panel in p['panels']:panel.pop('scene',None)
assert flattened==before
assets={};profiles=[]
for scene in script['scenes'].values():
 for bed in scene['beds']:
  file=chapter/bed['file'];assert page_sha256(file)==bed['sha256']
  with wave.open(str(file)) as f:
   duration=f.getnframes()/f.getframerate();pcm=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2')
  assert duration==bed['duration'];assert pcm[0]==pcm[-1]==0;assert bed['loop']==[0,duration]
  assets[bed['file']]={'bytes':file.stat().st_size,'duration':duration,'peak_after_gain_dbfs':float(20*np.log10(max(abs(pcm.astype(float)))/32768))+bed['gain_db']}
  profiles.append(bed['id'])
audit=read_json(chapter/'cache/music-scenes.json')
assert all(a['needs_review'] for p in audit['pages'] for a in p['assignments'])
result={'cold':cold,'warm':warm,'profiles':sorted(set(profiles)),'assets':assets,'asset_bytes':sum(a['bytes'] for a in assets.values()),
        'panel_assignments':sum(len(p['assignments']) for p in audit['pages']),'scene_ids':[[a['scene'] for a in p['assignments']] for p in audit['pages']],
        'source_hashes_unchanged':True,'reading_camera_events_unchanged':True,'published_v1_unchanged':True}
write_json(root/'reports/M3d2-golden.json',result);print(json.dumps(result,indent=2))
