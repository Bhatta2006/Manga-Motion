"""Owned low-cost tonal phrases and ambience; no models or downloaded recordings."""
import hashlib
import wave
import numpy as np
from pipeline.cache import page_sha256

RATE=24000
REVISION='local-tonal-phrases-1'
PROFILES={'calm':([48,55,52,57],[0,7,12]),'warm':([48,53,55,48],[0,4,7]),
          'sad':([45,41,48,43],[0,3,7]),'tense':([40,40,43,40],[0,1,7]),
          'mystery':([45,48,43,45],[0,5,10]),'bright':([60,55,57,53],[0,4,7]),
          'action':([45,48,43,45],[0,7,12])}
AMBIENCE={'wind','rain'}

def samples(bus,profile):
    if bus not in ('music','ambience') or profile not in (PROFILES if bus=='music' else AMBIENCE):
        raise ValueError('Unknown local bed profile')
    duration=12
    t=np.arange(RATE*duration,dtype=float)/RATE
    audio=np.zeros_like(t)
    if bus=='music':
        roots,intervals=PROFILES[profile]
        for i,root in enumerate(roots):
            distance=(t-(i+.5)*3+duration/2)%duration-duration/2
            envelope=np.exp(-(distance/1.15)**4)
            for note in intervals:
                frequency=round(440*2**((root+note-69)/12)*duration)/duration
                audio+=envelope*(np.sin(2*np.pi*frequency*t)+.16*np.sin(4*np.pi*frequency*t))*.18
        # Sparse soft melodic notes distinguish phrases from a constant drone.
        melody=[0,7,12,7,4 if profile in ('warm','bright') else 3,7,5,2]
        for i,note in enumerate(melody):
            delta=(t-i*1.5)%duration
            envelope=(1-np.exp(-delta*16))*np.exp(-delta*2.4)*(delta<1.45)
            frequency=round(440*2**((roots[i//2]+note+12-69)/12)*duration)/duration
            audio+=.12*envelope*np.sin(2*np.pi*frequency*t)
        if profile=='action':audio*=.75+.25*np.sin(2*np.pi*t/1.5)**2
    else:
        rng=np.random.default_rng(int(hashlib.sha256(profile.encode()).hexdigest()[:8],16))
        spectrum=np.fft.rfft(rng.normal(size=len(t)))
        freq=np.fft.rfftfreq(len(t),1/RATE)
        spectrum*=np.minimum(freq/25,1)/(1+(freq/(450 if profile=='wind' else 3500))**2)
        spectrum[0]=0
        audio=np.fft.irfft(spectrum,n=len(t))*(.8+.2*np.sin(2*np.pi*t/duration))
    edge=np.minimum(t/.08,1)*np.minimum((duration-t)/.08,1)
    audio*=edge
    audio*= (.75 if bus=='music' else .5)/max(float(np.max(np.abs(audio))),1e-9)
    audio[0]=audio[-1]=0
    return (audio*32767).astype('<i2')

class LocalTonalLibrary:
    revision=REVISION
    def __init__(self):self.ready={}
    def materialize(self,store,bus,profile):
        key=(bus,profile)
        previous=self.ready.get(key)
        if previous and store.asset(previous['file']).is_file() and page_sha256(store.asset(previous['file']))==previous['sha256']:
            return previous
        pcm=samples(bus,profile)
        recipe=hashlib.sha256((REVISION+bus+profile).encode()+pcm.tobytes()).hexdigest()
        relative=f'{bus}/{profile}-{recipe[:16]}.wav';target=store.asset(relative)
        valid=False
        if target.is_file():
            try:
                with wave.open(str(target),'rb') as f:
                    valid=f.getparams()[:3]==(1,2,RATE) and f.readframes(f.getnframes())==pcm.tobytes()
            except (wave.Error,EOFError):pass
        if not valid:
            target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.tmp')
            with wave.open(str(temp),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
            temp.replace(target)
        value={'file':relative,'duration':len(pcm)/RATE,'loop':[0,len(pcm)/RATE],'sha256':page_sha256(target),
               'bus':bus,'profile':profile,'recipe':REVISION,'source':'MangaMotion owned procedural tones/noise; no external recording',
               'license':'Project-generated; personal use authorized','sample_rate':RATE,
               'peak_dbfs':float(20*np.log10(max(abs(pcm.astype(float)))/32768)),
               'rms_dbfs':float(20*np.log10(np.sqrt(np.mean((pcm.astype(float)/32768)**2)))),
               'seam_step':int(abs(int(pcm[-1])-int(pcm[0])))}
        self.ready[key]=value
        return value
