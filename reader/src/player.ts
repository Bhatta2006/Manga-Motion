import type { Panel, LineEvent, SfxEvent } from './script-types';
import {SceneMusic} from './music';
import { clamp, durationOf, outputTime } from './core.js';
import {duckPoints,scheduleDuck} from './sfx.js';

export class AudioTimeline {
  readonly context=new AudioContext({latencyHint:'interactive'});
  readonly sfxGain=this.context.createGain();
  readonly voiceGain=this.context.createGain();
  readonly sfxDuck=this.context.createGain();
  readonly analyser=this.context.createAnalyser();
  readonly output=this.context.createGain();
  readonly music=new SceneMusic(this.context,this.output);
  readonly clips=new Map<string,AudioBuffer>();
  readonly prefetched=new Map<string,AudioBuffer>();private prefetchGeneration=0;private prefetchUrls:string[]=[];private prefetchActive=false;private downloads=new Map<string,Promise<AudioBuffer>>();
  private async decoded(url:string){
    if(this.prefetched.has(url))return this.prefetched.get(url)!;
    let task=this.downloads.get(url);if(!task){task=(async()=>{const response=await fetch(url);if(!response.ok)throw Error(String(response.status));return this.context.decodeAudioData(await response.arrayBuffer());})().finally(()=>this.downloads.delete(url));this.downloads.set(url,task);}return task;
  }
  async prefetch(panels:{panel:Panel;base:string}[]){
    ++this.prefetchGeneration;this.prefetchUrls=[...new Set(panels.slice(0,3).flatMap(({panel,base})=>panel.timeline.flatMap(e=>e.type==='line'?[base+e.audio]:e.type==='sfx'?[base+e.file]:[])))].slice(0,32);
    for(const key of this.prefetched.keys())if(!this.prefetchUrls.includes(key))this.prefetched.delete(key);
    if(this.prefetchActive)return;this.prefetchActive=true;const attempted=new Set<string>();let generation=this.prefetchGeneration;
    try{while(true){if(generation!==this.prefetchGeneration){generation=this.prefetchGeneration;attempted.clear();}const url=this.prefetchUrls.find(u=>!this.prefetched.has(u)&&!attempted.has(u));if(!url)break;attempted.add(url);
      try{const buffer=await this.decoded(url);if(!this.prefetchUrls.includes(url))continue;const bytes=[...this.prefetched.values()].reduce((n,b)=>n+b.length*b.numberOfChannels*4,0);if(!this.prefetched.has(url)&&bytes+buffer.length*buffer.numberOfChannels*4<=32*2**20)this.prefetched.set(url,buffer);}catch{/* Current-panel preparation exposes an actual missing clip. */}
    }}finally{this.prefetchActive=false;}
  }
  sources:AudioBufferSourceNode[]=[];
  private sourceGains=new Map<AudioBufferSourceNode,GainNode>();
  failures:string[]=[];
  startAt=0;offset=0;duration=1;transition=0;playing=false;generation=0;
  constructor(public assetBase='/chapter/') { this.output.gain.value=.8;this.output.connect(this.context.destination);this.analyser.fftSize=256;this.sfxGain.connect(this.sfxDuck);this.sfxDuck.connect(this.analyser);this.analyser.connect(this.output);this.voiceGain.gain.value=.6;this.voiceGain.connect(this.output); }
  sfxRms() { const values=new Float32Array(this.analyser.fftSize);this.analyser.getFloatTimeDomainData(values);return Math.sqrt(values.reduce((s,v)=>s+v*v,0)/values.length); }
  async unlock() { if (this.context.state!=='running') await this.context.resume(); }
  async prepare(panel:Panel) {
    const token=++this.generation;
    this.stopSources();this.playing=false;this.offset=0;this.failures=[];
    const events=panel.timeline.filter((e):e is LineEvent|SfxEvent=>e.type==='line'||e.type==='sfx');
    await Promise.all(events.map(async e=>{
      const path=e.type==='line'?e.audio:e.file;
      if (this.clips.has(path)) return;
      try {
        const buffer=await this.decoded(this.assetBase+path);
        if(token===this.generation) this.clips.set(path,buffer);
      } catch(error) { if(token===this.generation) this.failures.push(`Audio unavailable: ${path}`); }
    }));
    if(token!==this.generation) return false;
    const durations=Object.fromEntries([...this.clips].map(([k,v])=>[k,v.duration]));
    this.duration=durationOf(panel,durations);
    // Keep only this panel's clips. Voice assets can be large in later milestones.
    const keep=new Set(events.map(e=>e.type==='line'?e.audio:e.file));
    for(const key of this.clips.keys()) if(!keep.has(key)) this.clips.delete(key);
    return true;
  }
  async play(panel:Panel,transition:number) {
    const token=this.generation;
    await this.unlock();
    if(token!==this.generation)return;
    this.stopSources();this.transition=transition;
    this.startAt=this.context.currentTime+.02-this.offset;
    this.playing=true;
    this.music.play(panel,Object.fromEntries([...this.clips].map(([k,v])=>[k,v.duration])),transition,this.offset);
    scheduleDuck(this.sfxDuck.gain,duckPoints(panel,Object.fromEntries([...this.clips].map(([k,v])=>[k,v.duration])),transition),this.offset,this.context.currentTime+.02);
    const length=this.duration+transition;
    // A silent buffer keeps a genuine output-device clock even on silent panels.
    const silent=this.context.createBuffer(1,this.context.sampleRate,this.context.sampleRate);
    const carrier=this.context.createBufferSource();carrier.buffer=silent;carrier.loop=true;carrier.connect(this.context.destination);
    carrier.start(this.context.currentTime+.02);
    carrier.stop(this.context.currentTime+.02+Math.max(0,length-this.offset));this.sources.push(carrier);
    for(const event of panel.timeline) {
      if(event.type==='camera') continue;
      const buffer=this.clips.get(event.type==='line'?event.audio:event.file);
      if(!buffer) continue;
      const t=event.t+transition;
      if(t+buffer.duration<=this.offset) continue;
      const source=this.context.createBufferSource();source.buffer=buffer;
      const gain=this.context.createGain();gain.gain.value=event.type==='sfx'?10**(event.gain_db/20):1;
      this.sourceGains.set(source,gain);
      source.connect(gain);gain.connect(event.type==='sfx'?this.sfxGain:this.voiceGain);
      const skipped=Math.max(0,this.offset-t);
      source.onended=()=>{source.disconnect();gain.disconnect();this.sourceGains.delete(source);};
      source.start(Math.max(this.context.currentTime+.02,this.startAt+t),skipped);this.sources.push(source);
    }
  }
  time() { return this.playing?clamp(outputTime(this.context,performance.now())-this.startAt,0,this.duration+this.transition):this.offset; }
  pause() { this.offset=this.time();this.playing=false;this.stopSources();this.music.pause(); }
  finish() { this.offset=this.duration+this.transition;this.playing=false;this.stopSources(); }
  cancel() { ++this.generation;this.playing=false;this.offset=0;this.stopSources(); }
  stopSources() { const now=this.context.currentTime;for(const source of this.sources) { try {const gain=this.sourceGains.get(source);if(gain){gain.gain.cancelAndHoldAtTime(now);gain.gain.linearRampToValueAtTime(0,now+.015);source.stop(now+.016);}else{source.stop();source.disconnect();}}catch{} } this.sources=[];this.sfxDuck.gain.cancelScheduledValues(now);this.sfxDuck.gain.setValueAtTime(1,now); }
}
