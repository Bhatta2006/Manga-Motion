import type { Panel, LineEvent, SfxEvent } from './types';
import { clamp, durationOf, outputTime } from './core.js';

export class AudioTimeline {
  readonly context=new AudioContext({latencyHint:'interactive'});
  readonly sfxGain=this.context.createGain();
  readonly voiceGain=this.context.createGain();
  readonly analyser=this.context.createAnalyser();
  readonly clips=new Map<string,AudioBuffer>();
  sources:AudioBufferSourceNode[]=[];
  failures:string[]=[];
  startAt=0;offset=0;duration=1;transition=0;playing=false;generation=0;
  constructor(public assetBase='/chapter/') { this.analyser.fftSize=256;this.sfxGain.connect(this.analyser);this.analyser.connect(this.context.destination);this.voiceGain.connect(this.context.destination); }
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
        const response=await fetch(this.assetBase+path);
        if(!response.ok) throw Error(`${response.status}`);
        const buffer=await this.context.decodeAudioData(await response.arrayBuffer());
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
      source.connect(gain);gain.connect(event.type==='sfx'?this.sfxGain:this.voiceGain);
      const skipped=Math.max(0,this.offset-t);
      source.onended=()=>{source.disconnect();gain.disconnect();};
      source.start(Math.max(this.context.currentTime+.02,this.startAt+t),skipped);this.sources.push(source);
    }
  }
  time() { return this.playing?clamp(outputTime(this.context,performance.now())-this.startAt,0,this.duration+this.transition):this.offset; }
  pause() { this.offset=this.time();this.playing=false;this.stopSources(); }
  finish() { this.offset=this.duration+this.transition;this.playing=false;this.stopSources(); }
  cancel() { ++this.generation;this.playing=false;this.offset=0;this.stopSources(); }
  stopSources() { for(const source of this.sources) { try {source.stop();}catch{} source.disconnect(); } this.sources=[]; }
}
