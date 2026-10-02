import { Application, Assets, Container, Graphics, Sprite, Texture } from 'pixi.js';
import Ajv from 'ajv';
import schema from '../../schema/motionscript-v1.schema.json';
import schemaV2 from '../../schema/motionscript-v2.schema.json';
import { validateSupportedScript } from './contract-v2.js';
import { clamp, ease, interpolate } from './core.js';
import { fit } from './camera';
import { SourcePlane } from './parallax';
import { AudioTimeline } from './player';
import type { MotionScript, Rect, Page } from './script-types';
import {canonicalSceneOffset,incomingTransition} from './music';
import { setPacing, playback } from './api';
import { FlowController } from './flow';
import {styledCamera,sceneEffects,shakeEligible,protectedShake} from './motion-settings.js';
import './motion.css';
export interface ReaderOptions {scriptUrl:string;assetBase:string;title:string;library?:boolean;series?:string;chapter?:string;readingWpm?:number|null;partial?:boolean;totalPages?:number;comparison?:boolean}
export async function startReader(options:ReaderOptions) {
const ajv=new Ajv({allErrors:true}),validators={1:ajv.compile(schema),2:ajv.compile(schemaV2)};

document.querySelector('#app')!.innerHTML=`
<header><div class="brand">MangaMotion <span>/ Motion study</span></div><div class="study">5 pages · original art</div></header>
<main><div class="stage-wrap"><div id="stage" role="button" tabindex="0" aria-label="Advance to next panel"></div><div id="caption"></div><div id="hint">Press Play to begin · tap the art to advance</div></div></main>
<footer><div class="progress"><span id="progress"></span></div><div class="transport"><div class="controls">
<button id="prev" aria-label="Previous panel">←</button><button id="play" class="primary">Play</button><button id="next" aria-label="Next panel">→</button><button id="replay" aria-label="Replay panel">↻</button><span id="position"></span>
</div><div class="options"><select id="mode" aria-label="Playback mode"><option value="tap">Tap paced</option><option value="auto">Auto play</option><option value="flow">Flow · swipe scenes</option></select><label id="speed-wrap">Reading speed <select id="speed" aria-label="Reading speed"><option value="160">Slow · 160 wpm</option><option value="240">Average · 240 wpm</option><option value="320">Fast · 320 wpm</option></select></label><button id="classic">Original page</button><label><input id="sfx" type="checkbox" checked>SFX</label><label><input id="reduce" type="checkbox">Reduce motion</label><label><input id="depth" type="checkbox" checked>Parallax</label></div></div>
<div class="note"><span id="status">Loading pages…</span><span id="error" role="status"></span></div></footer>`;

document.querySelector('.brand span')!.textContent='/ '+options.title;
if(options.library){const back=document.createElement('a');back.href='/';back.textContent='Library';back.className='library-link';document.querySelector('header')!.append(back);}
const $=<T extends HTMLElement>(id:string)=>document.getElementById(id)! as T;
const stage=$('stage'),status=$('status'),error=$('error');
const silentOption=document.createElement('option');silentOption.value='silent';silentOption.textContent='Silent auto';($('mode') as HTMLSelectElement).append(silentOption);
const sound=document.createElement('details');sound.className='sound-settings';
sound.innerHTML='<summary>Sound levels</summary><div class="sound-options"><label><input id="music-enable" type="checkbox" checked>Music <input id="music-level" aria-label="Music volume" type="range" min="0" max="100" value="100"></label><label><input id="ambience-enable" type="checkbox" checked>Ambience <input id="ambience-level" aria-label="Ambience volume" type="range" min="0" max="100" value="100"></label><label><input id="voice-enable" type="checkbox" checked>Voices <input id="voice-level" aria-label="Voice volume" type="range" min="0" max="100" value="100"></label><label>SFX <input id="sfx-level" aria-label="Sound effect volume" type="range" min="0" max="100" value="100"></label></div>';
document.querySelector('footer')!.append(sound);
if(options.comparison)$('caption').hidden=true;
const motionSelect=document.createElement('select');motionSelect.id='motion';motionSelect.setAttribute('aria-label','Motion strength');
motionSelect.innerHTML='<option value="subtle">Subtle motion</option><option value="normal" selected>Normal motion</option><option value="hype">Hype motion</option>';
document.querySelector('.options')!.prepend(motionSelect);
const vignette=document.createElement('div');vignette.className='scene-vignette';vignette.setAttribute('aria-hidden','true');stage.parentElement!.append(vignette);
const app=new Application();
const world=new Container();
const previousWorld=new Container(),previousMask=new Graphics().rect(0,0,1,1).fill(0xffffff),effectsOverlay=new Graphics();
const frameMask=new Graphics().rect(0,0,1,1).fill(0xffffff);
const plane=new SourcePlane();
const audio=new AudioTimeline(options.assetBase);
const textures=new Map<string,Texture>();
let script:MotionScript,index=0,ready=false,loading=false,classic=false,auto=false,reduce=false,depth=true;
let active:Sprite|null=null,previous:Rect|null=null,navigation=0,transition=0,pageFade=false;
let transitionKind='cut',motionPreset='normal',fxKey='',shakeActive=false;
let renderedRect:Rect|null=null;
let entries:{page:number;panel:number}[]=[];
let started=performance.now(),lastFrame=0,frameTimes:number[]=[],clockErrors:number[]=[],switches=0,glides=0;
const metrics={firstReadyMs:0,errors:[] as string[]};
let flow:FlowController|null=null;
const pageBases=new Map<string,string>();
let polling=false,pollTimer=0,closed=false,processingError='';
let sfxLevel=1;
window.addEventListener('pagehide',()=>{closed=true;clearTimeout(pollTimer);audio.pause();audio.music.cancel();void audio.context.close();},{once:true});

function current() {const e=entries[index],page=script.pages[e.page] as Page;return {page,panel:page.panels[e.panel]};}
function applyAudioLevels(){
  const silent=($('mode') as HTMLSelectElement).value==='silent';
  for(const bus of ['music','ambience'] as const)audio.music.setLevel(bus,silent||!($(`${bus}-enable`) as HTMLInputElement).checked?0:Number(($(`${bus}-level`) as HTMLInputElement).value)/100);
  const now=audio.context.currentTime;
  sfxLevel=silent||!($('sfx') as HTMLInputElement).checked?0:Number(($('sfx-level') as HTMLInputElement).value)/100;
  for(const [param,value] of [[audio.sfxGain.gain,silent||!($('sfx') as HTMLInputElement).checked?0:Number(($('sfx-level') as HTMLInputElement).value)/100],[audio.voiceGain.gain,silent||!($('voice-enable') as HTMLInputElement).checked?0:.6*Number(($('voice-level') as HTMLInputElement).value)/100]] as const){param.cancelAndHoldAtTime(now);param.linearRampToValueAtTime(value,now+.02);}
}
function rectNow():Rect {return styledCamera(current().panel,Math.max(0,audio.time()-transition),motionPreset,reduce);}
function updateHud() {
  const e=entries[index],{page,panel}=current();
  $('position').textContent=`Page ${e.page+1} · panel ${e.panel+1}/${page.panels.length}`;
  $('caption').textContent=classic?'Original page':`${panel.timeline.find(t=>t.type==='camera')?.move.replaceAll('_',' ')??'hold'} · ${panel.director.shot}`;
  $('play').textContent=audio.playing?'Pause':'Play';
  ($('prev') as HTMLButtonElement).disabled=index===0;
  ($('next') as HTMLButtonElement).disabled=index===entries.length-1;
  status.textContent=plane.sprite?'Source-only parallax available · visual preview':'Camera motion · parallax gated: no safe foreground region';
  error.textContent=[...audio.failures,...audio.music.failures,current().panel.layers?.length?'Character layers are not supported by this reader yet; showing original flat art.':'',processingError].filter(Boolean).join(' · ');
  document.querySelector('.study')!.textContent=options.partial?`${script.pages.length}/${options.totalPages} pages ready`:`${script.pages.length} pages · original art`;
  const mode=($('mode') as HTMLSelectElement).value;
  stage.setAttribute('aria-label',mode==='tap'?'Advance to next panel':'Pause or resume scene');
  $('hint').textContent=classic?'Original art · press Motion view to return':index===entries.length-1&&audio.offset>=audio.duration?(options.partial?'Waiting for next page…':'Chapter complete · replay or return to page 1'):mode==='flow'?'Swipe up for next · tap to pause':audio.playing?(auto?'Tap to pause · Auto follows reading time':'Tap the art to advance'):'Play to begin';
  $('hint').style.opacity=audio.playing?'0':'1';
}
async function show(next:number,play=false,replay=false) {
  if(next<0||next>=entries.length) return;
  const token=++navigation;
  const old=index;
  const oldRect=ready&&!classic?rectNow():null;
  const oldTexture=active?.texture;
  audio.cancel();loading=true;index=next;ready=false;
  error.textContent='';status.textContent='Loading panel…';
  try {
    const {page,panel}=current();
    const base=pageBases.get(page.id)??options.assetBase;
    audio.assetBase=base;
    const url=base+page.image;
    let texture=textures.get(url);
    if(!texture) {texture=await Assets.load<Texture>(url);textures.set(url,texture);}
    if(token!==navigation) return;
    const scene=script.version===2?panel.scene:null;
    const [panelReady,music]=await Promise.all([audio.prepare(panel),audio.music.prepare(scene??null,script.version===2&&scene?script.scenes[scene].beds:[],base)]);
    if(!panelReady||!music||token!==navigation)return;
    audio.music.select(music,canonicalSceneOffset(script,index,Object.fromEntries([...audio.clips].map(([k,v])=>[k,v.duration]))),next===old+1&&!replay,play&&!classic);
    plane.destroy();active?.destroy({texture:false,textureSource:false});
    previousWorld.removeChildren().forEach(child=>child.destroy({texture:false,textureSource:false}));
    active=new Sprite(texture);world.addChild(active);
    plane.prepare(texture,panel);if(plane.sprite)world.addChild(plane.sprite);
    // ±1 page cache; release old TextureSources explicitly. No models in reader.
    for(const [key,value] of textures) {
      const pageIndex=script.pages.findIndex(p=>(pageBases.get(p.id)??options.assetBase)+p.image===key);
      if(Math.abs(pageIndex-entries[index].page)>1) {await Assets.unload(key);textures.delete(key);}
    }
    if(token!==navigation)return;
    previous=oldRect&&entries[old].page===entries[next].page&&!replay?oldRect:null;
    pageFade=oldRect!==null&&entries[old].page!==entries[next].page&&!reduce;
    transitionKind=previous?script.pages[entries[old].page].panels[entries[old].panel].transition_out.type:pageFade?'fade':'cut';
    transition=reduce||replay?0:next===old+1?incomingTransition(script,next):previous&&transitionKind!=='cut'?script.pages[entries[old].page].panels[entries[old].panel].transition_out.dur:pageFade?.2:0;
    if(transition&&previous&&transitionKind!=='glide'&&oldTexture)previousWorld.addChild(new Sprite(oldTexture));
    if(transition)glides++;
    ready=true;loading=false;switches++;
    flow?.sync(index);
    if(!metrics.firstReadyMs)metrics.firstReadyMs=performance.now()-started;
    if(play&&!classic)await audio.play(panel,transition);
    if(token===navigation)updateHud();
  } catch(e) {
    if(token!==navigation)return;
    loading=false;error.textContent=`Could not load panel: ${String(e)}`;metrics.errors.push(String(e));status.textContent='Replay to retry';
    audio.music.pause();
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
stage.onclick=()=>void action(()=>auto?togglePlay():advance(1));
stage.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();void action(()=>auto?togglePlay():advance(1));}};
$('mode').onchange=()=>{const mode=($('mode') as HTMLSelectElement).value;auto=mode==='auto'||mode==='silent';applyAudioLevels();flow?.setEnabled(mode==='flow'||(auto&&matchMedia('(max-width:650px)').matches));if(auto&&!audio.playing)void action(togglePlay);updateHud();};
$('speed').onchange=()=>void action(async()=>{
  if(!options.series||!options.chapter)return;
  const control=$('speed') as HTMLSelectElement;
  audio.pause();updateHud();control.disabled=true;status.textContent='Updating reading time…';
  try {
    const info=await setPacing(options.series,options.chapter,Number(control.value));
    const response=await fetch(info.script_url);if(!response.ok)throw Error('New timing is unavailable');
    const data=await response.json();
    const next=await validateSupportedScript(data,validators) as MotionScript;
    if(JSON.stringify(next.pages.map(p=>[p.id,p.image,p.size,p.panels.map(q=>q.id)]))!==JSON.stringify(script.pages.map(p=>[p.id,p.image,p.size,p.panels.map(q=>q.id)])))throw Error('Chapter changed; reopen it from Library');
    script=next;options.scriptUrl=info.script_url;options.readingWpm=info.reading_wpm;
    // Original assets are immutable; existing textures remain valid, audio's
    // snapshot is unchanged because pacing introduces no new audio assets.
    await show(index,false,true);
  }catch(e){error.textContent=String(e);control.value=String(options.readingWpm??240);}
  finally{control.disabled=false;}
});
$('sfx').onchange=applyAudioLevels;
for(const id of ['music-enable','ambience-enable','voice-enable','music-level','ambience-level','voice-level','sfx-level'])$(id).oninput=applyAudioLevels;
$('reduce').onchange=()=>{reduce=($('reduce') as HTMLInputElement).checked;updateHud();};
motionSelect.onchange=()=>{motionPreset=motionSelect.value;};
$('depth').onchange=()=>{depth=($('depth') as HTMLInputElement).checked;};
$('classic').onclick=()=>{if(!ready)return;audio.pause();classic=!classic;$('classic').textContent=classic?'Motion view':'Original page';flow?.setEnabled(!classic&&(($('mode') as HTMLSelectElement).value==='flow'||(auto&&matchMedia('(max-width:650px)').matches)));updateHud();};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&ready){audio.pause();updateHud();}});
document.addEventListener('keydown',e=>{
  if(!script||!ready)return;
  if((e.target as HTMLElement).matches('input,select,button,#stage,.flow-rail'))return;
  if(e.key===' '){e.preventDefault();void action(togglePlay);}
  if(e.key==='ArrowLeft')void action(()=>advance(script.direction==='rtl'?1:-1));
  if(e.key==='ArrowRight')void action(()=>advance(script.direction==='rtl'?-1:1));
});

async function init() {
  const response=await fetch(options.scriptUrl);if(!response.ok)throw Error('Chapter playback is unavailable; return to Library and retry');
  const data=await response.json();
  script=await validateSupportedScript(data,validators) as MotionScript;entries=script.pages.flatMap((p,page)=>p.panels.map((_,panel)=>({page,panel})));
  for(const bus of ['music','ambience'] as const){const available=script.version===2&&Object.values(script.scenes).some(s=>s.beds.some(b=>b.bus===bus));($(`${bus}-enable`) as HTMLInputElement).disabled=!available;($(`${bus}-enable`) as HTMLInputElement).checked=available;}
  const hasVoice=script.pages.some(p=>p.panels.some(q=>q.timeline.some(e=>e.type==='line')));($('voice-enable') as HTMLInputElement).disabled=!hasVoice;($('voice-enable') as HTMLInputElement).checked=hasVoice;
  for(const page of script.pages)pageBases.set(page.id,options.assetBase);
  document.querySelector('.study')!.textContent=`${script.pages.length} pages · original art`;
  const hasSfx=script.pages.some(p=>p.panels.some(panel=>panel.timeline.some(event=>event.type==='sfx')));
  const sfxControl=$('sfx') as HTMLInputElement;
  sfxControl.disabled=!hasSfx;sfxControl.checked=hasSfx;
  sfxControl.parentElement!.title=hasSfx?'Play this chapter’s sound effects':'This chapter has no sound effects yet';
  if(!hasSfx){sfxControl.parentElement!.lastChild!.textContent='No SFX';audio.sfxGain.gain.value=0;}
  applyAudioLevels();
  ($('mode') as HTMLSelectElement).options[1].textContent=options.readingWpm?'Auto':'Auto (preview)';
  $('speed-wrap').hidden=!options.series||!!options.comparison;
  const speed=$('speed') as HTMLSelectElement;
  if(options.readingWpm&&!Array.from(speed.options).some(o=>o.value===String(options.readingWpm)))speed.add(new Option(`${options.readingWpm} wpm`,String(options.readingWpm)));
  speed.value=String(options.readingWpm??240);
  depth=script.pages.some(p=>p.panels.some(panel=>panel.director.focus.some(f=>f.ref==='parallax-safe')));
  ($('depth') as HTMLInputElement).checked=depth;($('depth') as HTMLInputElement).disabled=!depth;
  $('depth').title=depth?'Source-only foreground motion':'No safe foreground region on these pages';
  await app.init({resizeTo:stage,background:0x171d1f,preference:'webgl',powerPreference:'low-power',antialias:false,resolution:Math.min(devicePixelRatio,2),autoDensity:true});
  stage.appendChild(app.canvas);app.stage.addChild(previousWorld,previousMask,world,frameMask,effectsOverlay);world.mask=frameMask;previousWorld.mask=previousMask;
  flow=new FlowController(stage.parentElement!,entries.length,
    next=>{if(!loading&&next!==index)void action(()=>show(next,true));else flow?.sync(index);},
    ()=>{if(loading)return;audio.pause();auto=false;($('mode') as HTMLSelectElement).value='flow';applyAudioLevels();void action(()=>{});updateHud();},
    wasPlaying=>{if(wasPlaying)updateHud();else void action(togglePlay);},()=>audio.playing);
  if(matchMedia('(max-width:650px)').matches){($('mode') as HTMLSelectElement).value='flow';flow.setEnabled(true);}
  reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;($('reduce') as HTMLInputElement).checked=reduce;
  app.ticker.add(()=>{
    const now=performance.now();if(lastFrame&&ready&&audio.playing){frameTimes.push(now-lastFrame);if(frameTimes.length>3600)frameTimes.shift();}lastFrame=now;
    if(!ready)return;
    const {page,panel}=current(),time=audio.time();
    let rect:Rect;
    if(classic)rect=[0,0,...page.size];
    else if(reduce)rect=styledCamera(panel,0,motionPreset,true);
    else if(previous&&time<transition&&transitionKind==='glide')rect=interpolate(previous,styledCamera(panel,0,motionPreset),ease(time/transition,'inOutSine')) as Rect;
    else rect=styledCamera(panel,Math.max(0,time-transition),motionPreset);
    const frame=fit(world,rect,app.screen.width,app.screen.height);
    renderedRect=[...rect];
    frameMask.scale.set(frame.width,frame.height);
    frameMask.position.set((app.screen.width-frame.width)/2,(app.screen.height-frame.height)/2);
    const crossfade=!!previous&&transitionKind!=='glide'&&time<transition&&!classic&&!reduce;
    previousWorld.visible=crossfade;
    if(crossfade&&previous){const oldFrame=fit(previousWorld,previous,app.screen.width,app.screen.height);previousMask.scale.set(oldFrame.width,oldFrame.height);previousMask.position.set((app.screen.width-oldFrame.width)/2,(app.screen.height-oldFrame.height)/2);previousWorld.alpha=1-clamp(time/transition);}
    world.alpha=!classic&&!reduce&&(pageFade||crossfade)?clamp(time/transition):1;
    shakeActive=!classic&&!reduce&&time>=transition&&shakeEligible(page,panel)&&protectedShake(panel,rect);
    const fx=sceneEffects(panel,time-transition,motionPreset,reduce||classic,shakeActive);
    world.position.x+=fx.dx*app.screen.width;world.position.y+=fx.dy*app.screen.height;
    const nextFxKey=[app.screen.width,app.screen.height,fx.flash,fx.vignette].join(',');
    if(nextFxKey!==fxKey){fxKey=nextFxKey;effectsOverlay.clear();if(fx.flash)effectsOverlay.rect(0,0,app.screen.width,app.screen.height).fill({color:0xffffff,alpha:fx.flash});vignette.style.opacity=String(fx.vignette*4);}
    plane.update(clamp((time-transition)/audio.duration),depth&&!reduce&&!classic);
    $('progress').style.width=((index+clamp(time/(audio.duration+transition)))/entries.length*100)+'%';
    const activeLine=panel.timeline.find(e=>e.type==='line'&&time-transition>=e.t&&time-transition<e.t+e.dur);
    // Future dialogue events already play through the voice bus and share the clock.
    if(activeLine?.type==='line')$('caption').textContent=activeLine.text;
    if(audio.playing){clockErrors.push(Math.abs(audio.time()-time)*1000);if(clockErrors.length>3600)clockErrors.shift();}
    if(audio.playing&&time>=audio.duration+transition-.001){audio.finish();if(auto&&index<entries.length-1)void show(index+1,true);else{audio.music.pause();updateHud();}}
  });
  await show(0);
  async function refreshPages(){
    if(closed||polling||!options.partial||!options.series||!options.chapter)return;
    polling=true;
    try{
      const info=await playback(options.series,options.chapter);
      processingError=info.processing_error?`Processing paused: ${info.processing_error}`:'';
      options.totalPages=info.total_pages;
      if(info.script_url!==options.scriptUrl){
        const response=await fetch(info.script_url);if(!response.ok)throw Error('New pages are unavailable');
        const next=await validateSupportedScript(await response.json(),validators) as MotionScript;
        if(next.version!==script.version||JSON.stringify(next.characters)!==JSON.stringify(script.characters)||
           (script.version===2&&next.version===2&&Object.entries(script.scenes).some(([id,scene])=>JSON.stringify(next.scenes[id])!==JSON.stringify(scene)))||
           next.chapter!==script.chapter||next.direction!==script.direction||next.pages.length<script.pages.length||
           JSON.stringify(next.pages.slice(0,script.pages.length))!==JSON.stringify(script.pages))throw Error('Saved scenes changed; reopen the chapter to use the new version');
        const oldCount=entries.length;
        for(const page of next.pages.slice(script.pages.length))pageBases.set(page.id,info.asset_base);
        script=next;entries=script.pages.flatMap((p,page)=>p.panels.map((_,panel)=>({page,panel})));
        for(const bus of ['music','ambience'] as const)if(script.version===2&&Object.values(script.scenes).some(s=>s.beds.some(b=>b.bus===bus))){const control=$(`${bus}-enable`) as HTMLInputElement;if(control.disabled){control.disabled=false;control.checked=true;applyAudioLevels();}}
        flow?.setCount(entries.length);flow?.sync(index);options.scriptUrl=info.script_url;
        if(auto&&ready&&!loading&&index===oldCount-1&&audio.offset>=audio.duration+transition&&index<entries.length-1)void show(index+1,true);
      }
      options.partial=info.partial;
      if(ready)updateHud();
    }catch(e){processingError=String(e);if(ready)updateHud();}
    finally{polling=false;if(!closed&&options.partial)pollTimer=window.setTimeout(()=>void refreshPages(),1500);}
  }
  if(options.partial)pollTimer=window.setTimeout(()=>void refreshPages(),1500);
  // Read-only diagnostics for reproducible browser acceptance measurements.
  Object.defineProperty(window,'mangaMotionDiagnostics',{get:()=>({ready,loading,index,pages:script.pages.length,panels:entries.length,partial:options.partial,playing:audio.playing,time:audio.time(),duration:audio.duration+transition,classic,reduce,depth,auto,motionPreset,shakeActive,transitionKind,renderedRect,viewport:[app.screen.width,app.screen.height],loadedTextures:textures.size,frameTimes:[...frameTimes],visualClockSampleErrorMs:[...clockErrors],switches,glides,audioState:audio.context.state,sfxMuted:sfxLevel===0,sfxLevel,sfxRenderedGain:audio.sfxGain.gain.value,sfxRms:audio.sfxRms(),...audio.music.diagnostics(),parallaxAvailable:!!plane.sprite,...metrics})});
}
await init().catch(e=>{error.textContent=String(e);metrics.errors.push(String(e));status.textContent='Preview unavailable';});
}
