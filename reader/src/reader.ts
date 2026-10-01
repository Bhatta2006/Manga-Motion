import { Application, Assets, Container, Graphics, Sprite, Texture } from 'pixi.js';
import Ajv from 'ajv';
import schema from '../../schema/motionscript-v1.schema.json';
import { validateMotionScript } from './contract.js';
import { cameraAt, clamp, ease, interpolate } from './core.js';
import { fit } from './camera';
import { SourcePlane } from './parallax';
import { AudioTimeline } from './player';
import type { MotionScript, Rect } from './types';
export interface ReaderOptions {scriptUrl:string;assetBase:string;title:string;library?:boolean}
export async function startReader(options:ReaderOptions) {

document.querySelector('#app')!.innerHTML=`
<header><div class="brand">MangaMotion <span>/ Motion study</span></div><div class="study">5 pages · original art</div></header>
<main><div class="stage-wrap"><div id="stage" role="button" tabindex="0" aria-label="Advance to next panel"></div><div id="caption"></div><div id="hint">Press Play to begin · tap the art to advance</div></div></main>
<footer><div class="progress"><span id="progress"></span></div><div class="transport"><div class="controls">
<button id="prev" aria-label="Previous panel">←</button><button id="play" class="primary">Play</button><button id="next" aria-label="Next panel">→</button><button id="replay" aria-label="Replay panel">↻</button><span id="position"></span>
</div><div class="options"><select id="mode" aria-label="Playback mode"><option value="tap">Tap paced</option><option value="auto">Auto play</option></select><button id="classic">Original page</button><label><input id="sfx" type="checkbox" checked>SFX</label><label><input id="reduce" type="checkbox">Reduce motion</label><label><input id="depth" type="checkbox" checked>Parallax</label></div></div>
<div class="note"><span id="status">Loading pages…</span><span id="error" role="status"></span></div></footer>`;

document.querySelector('.brand span')!.textContent='/ '+options.title;
if(options.library){const back=document.createElement('a');back.href='/';back.textContent='Library';back.className='library-link';document.querySelector('header')!.append(back);}
const $=<T extends HTMLElement>(id:string)=>document.getElementById(id)! as T;
const stage=$('stage'),status=$('status'),error=$('error');
const app=new Application();
const world=new Container();
const frameMask=new Graphics().rect(0,0,1,1).fill(0xffffff);
const plane=new SourcePlane();
const audio=new AudioTimeline(options.assetBase);
const textures=new Map<string,Texture>();
let script:MotionScript,index=0,ready=false,loading=false,classic=false,auto=false,reduce=false,depth=true;
let active:Sprite|null=null,previous:Rect|null=null,navigation=0,transition=0,pageFade=false;
let renderedRect:Rect|null=null;
let entries:{page:number;panel:number}[]=[];
let started=performance.now(),lastFrame=0,frameTimes:number[]=[],clockErrors:number[]=[],switches=0,glides=0;
const metrics={firstReadyMs:0,errors:[] as string[]};

function current() {const e=entries[index];return {page:script.pages[e.page],panel:script.pages[e.page].panels[e.panel]};}
function rectNow():Rect {return cameraAt(current().panel,Math.max(0,audio.time()-transition)) as Rect;}
function updateHud() {
  const e=entries[index],{page,panel}=current();
  $('position').textContent=`Page ${e.page+1} · panel ${e.panel+1}/${page.panels.length}`;
  $('caption').textContent=classic?'Original page':`${panel.timeline.find(t=>t.type==='camera')?.move.replaceAll('_',' ')??'hold'} · ${panel.director.shot}`;
  $('play').textContent=audio.playing?'Pause':'Play';
  ($('prev') as HTMLButtonElement).disabled=index===0;
  ($('next') as HTMLButtonElement).disabled=index===entries.length-1;
  status.textContent=plane.sprite?'Source-only parallax available · visual preview':'Camera motion · parallax gated: no safe foreground region';
  error.textContent=audio.failures.join(' · ');
  $('hint').textContent=classic?'Original art · press Motion view to return':audio.playing?'Tap the art to advance':index===entries.length-1&&audio.offset>=audio.duration?'Preview complete · replay or return to page 1':'Play / replay · tap the art for the next panel';
  $('hint').style.opacity=audio.playing?'0':'1';
}
async function show(next:number,play=false,replay=false) {
  if(next<0||next>=entries.length) return;
  const token=++navigation;
  const old=index;
  const oldRect=ready&&!classic?rectNow():null;
  audio.cancel();loading=true;index=next;ready=false;
  error.textContent='';status.textContent='Loading panel…';
  try {
    const {page,panel}=current();
    const url=options.assetBase+page.image;
    let texture=textures.get(url);
    if(!texture) {texture=await Assets.load<Texture>(url);textures.set(url,texture);}
    if(token!==navigation) return;
    if(!await audio.prepare(panel)||token!==navigation) return;
    plane.destroy();active?.destroy({texture:false,textureSource:false});
    active=new Sprite(texture);world.addChild(active);
    plane.prepare(texture,panel);if(plane.sprite)world.addChild(plane.sprite);
    // ±1 page cache; release old TextureSources explicitly. No models in reader.
    for(const [key,value] of textures) {
      const pageIndex=script.pages.findIndex(p=>options.assetBase+p.image===key);
      if(Math.abs(pageIndex-entries[index].page)>1) {await Assets.unload(key);textures.delete(key);}
    }
    if(token!==navigation)return;
    previous=oldRect&&entries[old].page===entries[next].page&&!replay?oldRect:null;
    pageFade=oldRect!==null&&entries[old].page!==entries[next].page&&!reduce;
    transition=previous&&!reduce?script.pages[entries[old].page].panels[entries[old].panel].transition_out.dur:pageFade ? .2 : 0;
    if(transition)glides++;
    ready=true;loading=false;switches++;
    if(!metrics.firstReadyMs)metrics.firstReadyMs=performance.now()-started;
    if(play&&!classic)await audio.play(panel,transition);
    if(token===navigation)updateHud();
  } catch(e) {
    if(token!==navigation)return;
    loading=false;error.textContent=`Could not load panel: ${String(e)}`;metrics.errors.push(String(e));status.textContent='Replay to retry';
  }
}
async function togglePlay() {
  if(loading)return;
  if(!ready) {await show(index,true,true);return;}
  if(classic){classic=false;$('classic').textContent='Original page';}
  if(audio.playing)audio.pause();
  else if(audio.offset>=audio.duration+transition)await show(index,true,true);
  else await audio.play(current().panel,transition);
  updateHud();
}
function advance(delta:number) {if(classic){classic=false;$('classic').textContent='Original page';}void show(index+delta,true);}
async function action(fn:()=>void|Promise<void>) {try{await audio.unlock();await fn();}catch(e){error.textContent=String(e);metrics.errors.push(String(e));}}

$('play').onclick=()=>void action(togglePlay);
$('next').onclick=()=>void action(()=>advance(1));
$('prev').onclick=()=>void action(()=>advance(-1));
$('replay').onclick=()=>void action(()=>show(index,true,true));
stage.onclick=()=>void action(()=>advance(1));
stage.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();void action(()=>advance(1));}};
$('mode').onchange=()=>{auto=($('mode') as HTMLSelectElement).value==='auto';if(auto&&!audio.playing)void action(togglePlay);};
$('sfx').onchange=()=>{audio.sfxGain.gain.cancelScheduledValues(0);audio.sfxGain.gain.value=($('sfx') as HTMLInputElement).checked?1:0;};
$('reduce').onchange=()=>{reduce=($('reduce') as HTMLInputElement).checked;updateHud();};
$('depth').onchange=()=>{depth=($('depth') as HTMLInputElement).checked;};
$('classic').onclick=()=>{if(!ready)return;audio.pause();classic=!classic;$('classic').textContent=classic?'Motion view':'Original page';updateHud();};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&ready){audio.pause();updateHud();}});
document.addEventListener('keydown',e=>{
  if(!script||!ready)return;
  if((e.target as HTMLElement).matches('input,select,button,#stage'))return;
  if(e.key===' '){e.preventDefault();void action(togglePlay);}
  if(e.key==='ArrowLeft')void action(()=>advance(script.direction==='rtl'?1:-1));
  if(e.key==='ArrowRight')void action(()=>advance(script.direction==='rtl'?-1:1));
});

async function init() {
  const response=await fetch(options.scriptUrl);if(!response.ok)throw Error('Chapter playback is unavailable; return to Library and retry');
  const data=await response.json();const validate=new Ajv({allErrors:true}).compile(schema);
  script=validateMotionScript(data,validate) as MotionScript;entries=script.pages.flatMap((p,page)=>p.panels.map((_,panel)=>({page,panel})));
  document.querySelector('.study')!.textContent=`${script.pages.length} pages · original art`;
  depth=script.pages.some(p=>p.panels.some(panel=>panel.director.focus.some(f=>f.ref==='parallax-safe')));
  ($('depth') as HTMLInputElement).checked=depth;($('depth') as HTMLInputElement).disabled=!depth;
  $('depth').title=depth?'Source-only foreground motion':'No safe foreground region on these pages';
  await app.init({resizeTo:stage,background:0x171d1f,preference:'webgl',powerPreference:'low-power',antialias:false,resolution:Math.min(devicePixelRatio,2),autoDensity:true});
  stage.appendChild(app.canvas);app.stage.addChild(world,frameMask);world.mask=frameMask;
  reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;($('reduce') as HTMLInputElement).checked=reduce;
  app.ticker.add(()=>{
    const now=performance.now();if(lastFrame&&ready&&audio.playing){frameTimes.push(now-lastFrame);if(frameTimes.length>3600)frameTimes.shift();}lastFrame=now;
    if(!ready)return;
    const {page,panel}=current(),time=audio.time();
    let rect:Rect;
    if(classic)rect=[0,0,...page.size];
    else if(reduce)rect=(panel.timeline.find(e=>e.type==='camera') as {from:Rect}).from;
    else if(previous&&time<transition)rect=interpolate(previous,(panel.timeline.find(e=>e.type==='camera') as {from:Rect}).from,ease(time/transition,'inOutSine')) as Rect;
    else rect=cameraAt(panel,Math.max(0,time-transition)) as Rect;
    const frame=fit(world,rect,app.screen.width,app.screen.height);
    renderedRect=[...rect];
    frameMask.scale.set(frame.width,frame.height);
    frameMask.position.set((app.screen.width-frame.width)/2,(app.screen.height-frame.height)/2);
    world.alpha=pageFade&&!classic&&!reduce?clamp(time/.2):1;
    plane.update(clamp((time-transition)/audio.duration),depth&&!reduce&&!classic);
    $('progress').style.width=((index+clamp(time/(audio.duration+transition)))/entries.length*100)+'%';
    const activeLine=panel.timeline.find(e=>e.type==='line'&&time-transition>=e.t&&time-transition<e.t+e.dur);
    // Future dialogue events already play through the voice bus and share the clock.
    if(activeLine?.type==='line')$('caption').textContent=activeLine.text;
    if(audio.playing){clockErrors.push(Math.abs(audio.time()-time)*1000);if(clockErrors.length>3600)clockErrors.shift();}
    if(audio.playing&&time>=audio.duration+transition-.001){audio.finish();if(auto&&index<entries.length-1)void show(index+1,true);else updateHud();}
  });
  await show(0);
  // Read-only diagnostics for reproducible browser acceptance measurements.
  Object.defineProperty(window,'mangaMotionDiagnostics',{get:()=>({ready,loading,index,pages:script.pages.length,panels:entries.length,playing:audio.playing,time:audio.time(),duration:audio.duration+transition,classic,reduce,depth,auto,renderedRect,viewport:[app.screen.width,app.screen.height],loadedTextures:textures.size,frameTimes:[...frameTimes],visualClockSampleErrorMs:[...clockErrors],switches,glides,audioState:audio.context.state,sfxMuted:audio.sfxGain.gain.value===0,sfxRms:audio.sfxRms(),parallaxAvailable:!!plane.sprite,...metrics})});
}
await init().catch(e=>{error.textContent=String(e);metrics.errors.push(String(e));status.textContent='Preview unavailable';});
}
