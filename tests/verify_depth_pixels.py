"""Compare real WebGL frames at a frozen shared camera clock."""
import json
import numpy as np
from PIL import Image
from pathlib import Path
root=Path(__file__).resolve().parents[1];result=json.loads((root/'reports/M4c2-browser.json').read_text())
def diff(name):
    a=np.array(Image.open(root/f'reports/M4c2-{name}-depth-private.png').convert('RGB'),dtype='int16');b=np.array(Image.open(root/f'reports/M4c2-{name}-flat-private.png').convert('RGB'),dtype='int16');return abs(a-b)
initial=diff('initial');posed=diff('posed');assert initial.max()<=1,'Rest pose must retain original raster within rounding'
assert np.any(posed>2),'A real rendered cutout must differ from flat rendering'
tx,ty,s=result['worldTransform'];h,w=posed.shape[:2];checks=[]
for box in result['protectedText']:
    x,y,r,b=box;l=max(0,int(np.floor(tx+x*s)));t=max(0,int(np.floor(ty+y*s)));rr=min(w,int(np.ceil(tx+r*s)));bb=min(h,int(np.ceil(ty+b*s)))
    if l<rr and t<bb:
        maximum=int(posed[t:bb,l:rr].max());assert maximum==0,'Depth changes protected text';checks.append(maximum)
x,y,r,b=result['sourceBBox'];pose=result['pose'][0];ax,ay=pose['position'];scale=pose['scale'];guard=2
allowed=np.zeros((h,w),bool);l=max(0,int(np.floor(tx+min(x,ax+(x-ax)*scale)*s))-guard);t=max(0,int(np.floor(ty+min(y,ay+(y-ay)*scale)*s))-guard);rr=min(w,int(np.ceil(tx+max(r,ax+(r-ax)*scale)*s))+guard);bb=min(h,int(np.ceil(ty+max(b,ay+(b-ay)*scale)*s))+guard);allowed[t:bb,l:rr]=True
assert posed[~allowed].max()==0,'Depth changes pixels outside the character envelope'
metrics={'initial_max_channel_delta':int(initial.max()),'posed_changed_pixels':int(np.any(posed>2,axis=2).sum()),'posed_max_channel_delta':int(posed.max()),'protected_text_max_deltas':checks,'outside_envelope_max_delta':int(posed[~allowed].max())}
(root/'reports/M4c2-pixels.json').write_text(json.dumps(metrics,indent=2)+'\n');print(metrics)
