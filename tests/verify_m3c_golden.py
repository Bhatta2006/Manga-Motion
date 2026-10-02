import json,os,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.build_motion import build_motion
from pipeline.store import read_json,write_json
from pipeline.cache import page_sha256
root=Path(__file__).resolve().parents[1];chapter=root/'library/golden-m1d/chapter';runtime=Path(os.environ['MANGAMOTION_RUNTIME'])
script,cold=build_motion(root/'library','golden-m1d','chapter',runtime)
_,warm=build_motion(root/'library','golden-m1d','chapter',runtime)
assert warm['sfx_stage']['cache_hits']==5
audio=read_json(chapter/'cache/scene-sfx.json');counts={};mix=[];assets={}
for page in audio['pages']:
 counts[page['page_sha256'][:8]]=len(page['events'])
 for asset in page['assets']:
  assert asset['license'] and asset['source'] and page_sha256(chapter/asset['file'])==asset['sha256'];assets[asset['file']]=asset
 for cue in page['events']:
  with wave.open(str(chapter/cue['event']['file'])) as f:pcm=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').astype(float)/32768
  signal=pcm*10**(cue['event']['gain_db']/20)
  mix.append({'category':cue['audit']['category'],'reason':cue['audit']['reason'],'peak_dbfs':20*np.log10(max(abs(signal))),
              'rms_dbfs':20*np.log10(np.sqrt(np.mean(signal**2)))})
assert sum(counts.values())>0 and all(n<=3 for n in counts.values())
assert all(page_sha256(chapter/p['image'])==p['page_sha256'] for p in read_json(chapter/'analysis.json')['pages'])
result={'cold':cold,'warm':warm,'cue_counts':counts,'unique_asset_bytes':sum((chapter/p).stat().st_size for p in assets),'mix':mix,
        'suppressed_conflicts':sum(len(p['review']) for p in audio['pages']),'source_hashes_unchanged':True}
write_json(root/'reports/M3c-golden.json',result)
print(json.dumps(result,indent=2))
