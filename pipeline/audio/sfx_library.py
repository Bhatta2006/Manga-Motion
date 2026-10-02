"""Owned deterministic PCM assets; small CPU-only catalog behind an adapter."""
import hashlib
import wave
import numpy as np
from pipeline.cache import page_sha256

RATE=24000
REVISION='procedural-scene-sfx-1'


def samples(category):
    duration={'impact':.55,'whoosh':.65,'footsteps':.8,'door':.7,'heartbeat':1,'rain':1.2,'wind':1.2,'chime':.7}.get(category)
    if duration is None:raise ValueError('Unknown scene SFX')
    t=np.arange(round(duration*RATE))/RATE
    noise=np.random.default_rng(int(hashlib.sha256(category.encode()).hexdigest()[:8],16)).normal(0,1,len(t))
    smooth=np.convolve(noise,np.ones(24)/24,mode='same')
    edge=np.minimum(t/.015,1)*np.minimum((duration-t)/.03,1)
    if category in ('wind','whoosh','rain'):
        audio=(smooth if category!='rain' else .5*noise+.5*smooth)*np.sin(np.pi*t/duration)**2
    elif category=='impact':audio=(np.sin(2*np.pi*(80*t-30*t*t))+.3*noise)*np.exp(-t*13)
    elif category=='chime':audio=(np.sin(2*np.pi*660*t)+.35*np.sin(2*np.pi*990*t))*np.exp(-t*8)
    elif category in ('heartbeat','footsteps'):
        audio=np.zeros_like(t)
        for onset in ((.04,.22,.7,.88) if category=='heartbeat' else (.05,.43)):
            delta=np.maximum(0,t-onset);pulse=(t>=onset)*np.exp(-delta*28)
            audio+=pulse*(np.sin(2*np.pi*(65 if category=='heartbeat' else 110)*delta)+(.12 if category=='heartbeat' else .3)*smooth)
    else:audio=(.4*np.sin(2*np.pi*(210*t+160*t*t))+.6*smooth)*np.exp(-t*6)
    audio*=edge;audio=audio/max(float(np.max(np.abs(audio))),1e-9)*.32
    audio[0]=audio[-1]=0
    return (audio*32767).astype('<i2')


class ProceduralSceneLibrary:
    revision=REVISION
    def materialize(self,store,category):
        pcm=samples(category);digest=hashlib.sha256(REVISION.encode()+category.encode()+pcm.tobytes()).hexdigest()
        relative=f'sfx/{category}-{digest[:16]}.wav';path=store.asset(relative)
        valid=False
        if path.is_file():
            try:
                with wave.open(str(path),'rb') as f:valid=f.getparams()[:3]==(1,2,RATE) and f.readframes(f.getnframes())==pcm.tobytes()
            except (wave.Error,EOFError):pass
        if not valid:
            path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
            with wave.open(str(temp),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
            temp.replace(path)
        return {'file':relative,'duration':len(pcm)/RATE,'sha256':page_sha256(path),
                'source':'MangaMotion owned procedural recipe; no third-party recording',
                'license':'MangaMotion project-generated asset; personal use authorized',
                'recipe':REVISION,'peak_dbfs':20*np.log10(max(abs(pcm.astype(float)))/32768)}
