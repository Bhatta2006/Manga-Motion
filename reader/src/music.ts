import type {Bed,MotionScript} from './script-types';
import {bytesHash} from './contract-v2.js';
import {outputTime,durationOf} from './core.js';
import {duckPoints,scheduleDuck} from './sfx.js';

type Clip={bed:Bed;buffer:AudioBuffer};
type Voice={clip:Clip;source:AudioBufferSourceNode;gain:GainNode;duck:GainNode;envelope:{start:number;duration:number;from:number;to:number;kind:'in'|'out'};stopped:boolean};
export function loopOffset(bed:Bed,elapsed:number){return bed.loop[0]+Math.max(0,elapsed)%(bed.loop[1]-bed.loop[0]);}
export function incomingTransition(script:MotionScript,index:number){
  if(index<=0)return 0;
  const entries=script.pages.flatMap((page,p)=>page.panels.map(panel=>({page:p,panel}))),previous=entries[index-1],current=entries[index];
  if(previous.page!==current.page)return .2;
  return previous.panel.transition_out.type==='cut'?0:previous.panel.transition_out.dur;
}
export function canonicalSceneOffset(script:MotionScript,index:number,durations:Record<string,number>={}){
  if(script.version!==2)return 0;
  const panels=script.pages.flatMap(p=>p.panels),scene=panels[index]?.scene;let start=index;
  if(!scene)return 0;
  while(start>0&&panels[start-1].scene===scene)start--;
  let value=0;
  for(let i=start;i<index;i++)value+=durationOf(panels[i],durations)+incomingTransition(script,i);
  return value;
}
function envelopeValue(v:Voice,time:number){const e=v.envelope,u=Math.max(0,Math.min(1,(time-e.start)/e.duration));return e.kind==='in'?e.from+(e.to-e.from)*Math.sin(u*Math.PI/2):e.to+(e.from-e.to)*Math.cos(u*Math.PI/2);}
export class SceneMusic {
  readonly buses:Record<'music'|'ambience',GainNode>;
  readonly analysers:Record<'music'|'ambience',AnalyserNode>;
  readonly buffers=new Map<string,AudioBuffer>();
  voices:Voice[]=[];prepared:Clip[]=[];scene:string|null=null;offset=0;origin=0;running=false;generation=0;starts=0;
  failures:string[]=[];private seekFade=false;
  constructor(readonly context:AudioContext,output:AudioNode){
    this.buses={music:context.createGain(),ambience:context.createGain()};this.analysers={music:context.createAnalyser(),ambience:context.createAnalyser()};
    for(const bus of ['music','ambience'] as const){this.analysers[bus].fftSize=256;this.buses[bus].connect(this.analysers[bus]);this.analysers[bus].connect(output);}
  }
  time(){return this.running?Math.max(this.offset,outputTime(this.context,performance.now())-this.origin):this.offset;}
  async prepare(id:string|null,beds:Bed[],base:string){
    const token=++this.generation,clips:Clip[]=[],failures:string[]=[];
    await Promise.all(beds.map(async bed=>{
      try{
        let buffer=this.buffers.get(bed.sha256);
        if(!buffer){const response=await fetch(base+bed.file);if(!response.ok)throw Error('Asset unavailable');const bytes=await response.arrayBuffer();
          if(await bytesHash(bytes)!==bed.sha256)throw Error('Asset hash mismatch');buffer=await this.context.decodeAudioData(bytes);}
        if(Math.abs(buffer.duration-bed.duration)>1/buffer.sampleRate||bed.loop[1]>buffer.duration+1/buffer.sampleRate)throw Error('Duration/loop mismatch');
        if(token===this.generation){this.buffers.set(bed.sha256,buffer);clips.push({bed,buffer});}
      }catch(e){failures.push(`Background audio unavailable: ${bed.file} (${String(e)})`);}
    }));
    if(token!==this.generation)return null;
    this.failures=failures;
    // Current scene's two buffers plus bounded retiring sources; no whole-chapter preload.
    const keep=new Set(clips.map(c=>c.bed.sha256));
    for(const key of this.buffers.keys())if(!keep.has(key))this.buffers.delete(key);
    return {id,clips};
  }
  select(prepared:{id:string|null;clips:Clip[]},offset:number,sequential:boolean,play:boolean){
    const continuous=sequential&&prepared.id===this.scene&&play;
    if(continuous){this.prepared=prepared.clips;return;}
    const same=prepared.id===this.scene;
    this.retire(same ? .05 : undefined);this.running=false;this.scene=prepared.id;this.offset=offset;this.prepared=prepared.clips;this.seekFade=same;
  }
  setLevel(bus:'music'|'ambience',level:number){const p=this.buses[bus].gain,now=this.context.currentTime;p.cancelAndHoldAtTime(now);p.linearRampToValueAtTime(Math.max(0,Math.min(1,level)),now+.02);}
  play(panel:Parameters<typeof duckPoints>[0],durations:Record<string,number>,transition:number,panelOffset=0){
    if(!this.running&&this.scene&&this.prepared.length){
      const now=this.context.currentTime+.02;this.origin=now-this.offset;this.running=true;
      for(const clip of this.prepared){
        const source=this.context.createBufferSource(),gain=this.context.createGain(),duck=this.context.createGain();
        source.buffer=clip.buffer;source.loop=true;source.loopStart=clip.bed.loop[0];source.loopEnd=clip.bed.loop[1];
        source.connect(gain);gain.connect(duck);duck.connect(this.buses[clip.bed.bus]);
        const voice:Voice={clip,source,gain,duck,envelope:{start:now,duration:this.seekFade ? .05 : clip.bed.fade_seconds,from:0,to:10**(clip.bed.gain_db/20),kind:'in'},stopped:false};
        source.onended=()=>{source.disconnect();gain.disconnect();duck.disconnect();this.voices=this.voices.filter(v=>v!==voice);};
        this.voices.push(voice);this.curve(voice);source.start(now,loopOffset(clip.bed,this.offset));this.starts++;
      }
      this.seekFade=false;
    }
    const points=duckPoints(panel,durations,transition);
    for(const voice of this.voices.filter(v=>!v.stopped)){
      const duck=10**(voice.clip.bed.duck_db/20);
      scheduleDuck(voice.duck.gain,points.map(([t,value])=>[t,value===.5?duck:1]),panelOffset,this.context.currentTime+.02);
    }
  }
  private curve(voice:Voice){
    const e=voice.envelope,curve=new Float32Array(65);
    for(let i=0;i<curve.length;i++)curve[i]=envelopeValue(voice,e.start+e.duration*i/(curve.length-1));
    // Piecewise equal-power ramps can be interrupted mid-fade without retaining
    // a truncated native value-curve event across a seek.
    const param=voice.gain.gain;param.cancelAndHoldAtTime(e.start);param.setValueAtTime(curve[0],e.start);
    for(let i=1;i<curve.length;i++)param.linearRampToValueAtTime(curve[i],e.start+e.duration*i/(curve.length-1));
  }
  private retire(seconds?:number){
    const now=this.context.currentTime;
    for(const voice of this.voices){
      const from=envelopeValue(voice,now);voice.stopped=true;
      const retiring=voice.envelope.kind==='out';
      voice.envelope={start:now,duration:retiring?.02:seconds??voice.clip.bed.fade_seconds,from,to:0,kind:'out'};
      this.curve(voice);voice.source.stop(now+voice.envelope.duration+.001);
    }
  }
  pause(){this.offset=this.time();this.running=false;this.retire(.02);this.seekFade=true;}
  cancel(){++this.generation;this.pause();}
  rms(bus:'music'|'ambience'){const data=new Float32Array(256);this.analysers[bus].getFloatTimeDomainData(data);return Math.sqrt(data.reduce((s,v)=>s+v*v,0)/data.length);}
  diagnostics(){return {scene:this.scene,musicTime:this.time(),musicRunning:this.running,musicStarts:this.starts,musicBuffers:this.buffers.size,musicSources:this.voices.length,
    musicRms:this.rms('music'),ambienceRms:this.rms('ambience'),musicMuted:this.buses.music.gain.value===0,ambienceMuted:this.buses.ambience.gain.value===0};}
}
