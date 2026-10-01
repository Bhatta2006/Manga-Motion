"""Owned, reproducible procedural preview accents. No model or cloud API."""
import hashlib
import json
import wave
from pathlib import Path
import numpy as np
from pipeline.cache import page_sha256

RATE = 24000
RECIPE = "procedural-sfx-1"


def samples(kind):
    duration = .48 if kind == 'wind' else .20 if kind == 'turn' else .30
    n = round(RATE*duration)
    t = np.arange(n)/RATE
    seed = int(hashlib.sha256(kind.encode()).hexdigest()[:8],16)
    noise = np.random.default_rng(seed).normal(0,1,n)
    smooth = np.convolve(noise,np.ones(24)/24,mode='same')
    envelope = np.sin(np.pi*t/duration)**2
    if kind in ('wind','turn'):
        audio = smooth*envelope
    elif kind == 'chime':
        audio = (np.sin(2*np.pi*880*t)+.4*np.sin(2*np.pi*1320*t))*np.exp(-t*15)*np.minimum(t/.008,1)
    else:
        raise ValueError(f'Unknown SFX category: {kind}')
    audio = audio/max(float(np.max(np.abs(audio))),1e-9)*.25
    audio[0]=audio[-1]=0
    return (audio*32767).astype('<i2')


def materialize(root, kind):
    pcm = samples(kind)
    key = hashlib.sha256(RECIPE.encode()+kind.encode()+pcm.tobytes()).hexdigest()
    name = f'sfx/{kind}-{key[:12]}.wav'
    path = root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    # Recreate missing/corrupted assets independently of cached page JSON.
    valid = False
    if path.exists():
        try:
            with wave.open(str(path),'rb') as f:
                valid = f.getframerate()==RATE and f.getnchannels()==1 and f.getsampwidth()==2 and f.readframes(f.getnframes())==pcm.tobytes()
        except (wave.Error,EOFError): pass
    if not valid:
        temp = path.with_suffix('.tmp')
        with wave.open(str(temp),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
        temp.replace(path)
    return {'file':name,'duration':len(pcm)/RATE,'pcm_sha256':hashlib.sha256(pcm.tobytes()).hexdigest(),'source':'MangaMotion procedural preview accent','recipe':RECIPE}


class ProceduralSfxAdapter:
    stage_name = 'preview-sfx'
    revision = RECIPE
    heavy = False
    def __init__(self, cues, assets): self.cues,self.assets=cues,assets
    def load(self): pass
    def unload(self): pass
    def run_page(self,page):
        return {'cues':[{'panel_index':p,'t':t,'type':'sfx','file':self.assets[kind]['file'],'gain_db':gain} for p,t,kind,gain in self.cues[page_sha256(page)]]}
