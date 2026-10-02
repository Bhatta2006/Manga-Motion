// Real golden assets through the actual browser and native offline audio graph.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';
import ts from 'typescript';
const project=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m3d3-'+process.pid),{
  channel:'msedge',headless:true,viewport:{width:1280,height:900},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[],result={};page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const at=i=>page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,i);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const open=async()=>{await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#mode').selectOption('tap');};
try{
  const info=await (await context.request.get(base+'/api/chapters/golden-m1d/chapter/playback')).json();
  const script=await (await context.request.get(base+info.script_url)).json();assert.equal(script.version,2);
  const panels=script.pages.flatMap(p=>p.panels);assert.equal(panels.length,25);
  await open();await page.locator('#play').click();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.musicRms>.0001&&window.mangaMotionDiagnostics.ambienceRms>.00001);
  const first=await diag();await page.locator('#next').click();await at(1);
  await page.waitForTimeout(1200);
  const steady=await diag(),frames=steady.frameTimes.toSorted((a,b)=>a-b);
  result.performance={frameSamples:frames.length,medianFrameMs:frames[Math.floor(frames.length*.5)],p95FrameMs:frames[Math.floor(frames.length*.95)],jsHeapBytes:await page.evaluate(()=>performance.memory?.usedJSHeapSize??null)};
  const second=await diag();assert.equal(panels[0].scene,panels[1].scene);assert.equal(second.musicStarts,first.musicStarts);assert.ok(second.musicTime>=first.musicTime);
  await page.locator('#play').click();await page.waitForTimeout(100);const paused=await diag();await page.waitForTimeout(180);const held=await diag();
  assert.equal(held.musicTime,paused.musicTime);assert.ok(held.musicRms<1e-8&&held.ambienceRms<1e-8);
  await page.locator('#play').click();await page.waitForTimeout(120);const resumed=await diag();assert.ok(resumed.musicTime>=held.musicTime);assert.ok(resumed.musicTime-held.musicTime<.3);
  result.continuity={sameSceneStarts:first.musicStarts,afterNextStarts:second.musicStarts,pausedOffset:held.musicTime,resumedOffset:resumed.musicTime};
  await page.locator('.sound-settings summary').click();await page.locator('#music-enable').uncheck();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.musicMuted&&window.mangaMotionDiagnostics.musicRms<1e-8);
  assert.ok((await diag()).ambienceRms>1e-6);await page.locator('#music-enable').check();await page.locator('#ambience-enable').uncheck();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.ambienceMuted&&window.mangaMotionDiagnostics.ambienceRms<1e-8);
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.musicRms>1e-5);await page.locator('#ambience-enable').check();
  await page.locator('#mode').selectOption('silent');await page.waitForFunction(()=>window.mangaMotionDiagnostics.musicMuted&&window.mangaMotionDiagnostics.ambienceMuted&&window.mangaMotionDiagnostics.sfxMuted);
  const silent=await diag();await page.waitForTimeout(120);assert.ok((await diag()).time>silent.time);await page.locator('#mode').selectOption('tap');
  await page.waitForFunction(()=>!window.mangaMotionDiagnostics.musicMuted&&!window.mangaMotionDiagnostics.ambienceMuted);
  result.controls='Independent music/ambience mutes; Silent Auto advances the audio clock; preferences restore';
  const sources=[];for(let i=2;i<25;i++){await page.locator('#next').click();await at(i);sources.push((await diag()).musicSources);assert.ok((await diag()).musicBuffers<=2);}
  assert.deepEqual((await diag()).errors,[]);result.navigation={panels:25,maxSources:Math.max(...sources),maxBuffers:(await diag()).musicBuffers};
  await page.locator('#prev').click();await at(23);await page.locator('#replay').click();await at(23);
  await page.setViewportSize({width:390,height:844});await open();assert.ok(await page.evaluate(()=>document.body.scrollWidth)<=390);
  result.mobile='390 px emulation: no horizontal overflow';
  for(const failure of ['missing','hash']){
    await page.route('**/music/*.wav',route=>failure==='missing'?route.fulfill({status:404,body:'missing'}):route.fulfill({body:Buffer.from('corrupt'),contentType:'audio/wav'}));
    await open();assert.match(await page.locator('#error').textContent(),/Background audio unavailable/);await page.locator('#play').click();await page.waitForTimeout(120);assert.ok((await diag()).time>0);
    assert.deepEqual((await diag()).errors,[]);await page.unroute('**/music/*.wav');
  }
  result.assetFailure='404 and hash mismatch warn while camera/audio clock continue';
  await page.goto(base+'/?series=preview&chapter=m0b');await ready();assert.equal(await page.locator('#music-enable').isDisabled(),true);result.v1='Legacy v1 remains readable without background music';
  // Load actual implementation modules; transpilation only erases TypeScript.
  await page.route('**/m3d3-module/*',async route=>{
    const name=new URL(route.request().url()).pathname.split('/').at(-1);assert.ok(['music.js','core.js','sfx.js','contract-v2.js','contract.js'].includes(name));
    const source=await fs.readFile(path.join(project,'reader/src',name==='music.js'?'music.ts':name),'utf8');
    await route.fulfill({contentType:'text/javascript',body:name==='music.js'?ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText:source});
  });
  console.log('Browser navigation, controls and failure checks passed; rendering native audio graph.');
  result.mix=await page.evaluate(async({script,assetBase})=>{
    const {SceneMusic,canonicalSceneOffset}=await import('/m3d3-module/music.js');
    const panels=script.pages.flatMap(p=>p.panels),ids=Object.keys(script.scenes),rate=96000;
    const ctx=new OfflineAudioContext(1,18*rate,rate),output=ctx.createGain();output.gain.value=.8;output.connect(ctx.destination);
    const music=new SceneMusic(ctx,output),first=await music.prepare(ids[0],script.scenes[ids[0]].beds,assetBase);
    // Same actual four golden SFX assets, placed away from fade/seam probes.
    let cueTime=1;
    for(const event of panels.flatMap(p=>p.timeline).filter(e=>e.type==='sfx')){
      const response=await fetch(assetBase+event.file);if(!response.ok)throw Error('SFX unavailable');
      const buffer=await ctx.decodeAudioData(await response.arrayBuffer()),source=ctx.createBufferSource(),gain=ctx.createGain();
      source.buffer=buffer;gain.gain.value=10**(event.gain_db/20);source.connect(gain);gain.connect(output);source.start(cueTime);cueTime+=3;
    }
    music.select(first,0,false,true);music.play(panels[0],{},0);
    const events=[.5,13,14,14.5,15,15.1,15.2,16].map(t=>ctx.suspend(t));const rendered=ctx.startRendering();
    await events[0];const starts=music.starts;music.select(first,100,true,true);music.play(panels[1],{},0);if(music.starts!==starts)throw Error('Sequential reset');await ctx.resume();
    await events[1];const next=await music.prepare(ids[1],script.scenes[ids[1]].beds,assetBase);music.select(next,0,false,true);music.play(panels[0],{},0);await ctx.resume();
    await events[2];music.pause();const offset=music.offset;await ctx.resume();
    await events[3];if(music.offset!==offset)throw Error('Paused phase moved');music.play(panels[0],{},0);await ctx.resume();
    let maxSources=0;
    for(let i=4;i<=6;i++){await events[i];music.select(i%2?first:next,0,false,true);music.play(panels[0],{},0);maxSources=Math.max(maxSources,music.voices.length);await ctx.resume();}
    await events[7];music.select(next,canonicalSceneOffset(script,1),false,true);music.play(panels[1],{},0);await ctx.resume();
    const data=(await rendered).getChannelData(0);let peak=0,maxDelta=0,maxDeltaTime=0;for(let i=1;i<data.length;i++){peak=Math.max(peak,Math.abs(data[i]));const delta=Math.abs(data[i]-data[i-1]);if(delta>maxDelta){maxDelta=delta;maxDeltaTime=i/rate;}}
    const rms=(a,b)=>{let sum=0;for(let i=Math.floor(a*rate);i<b*rate;i++)sum+=data[i]**2;return Math.sqrt(sum/((b-a)*rate));};
    const seam=(t)=>{let max=0;for(let i=Math.floor((t-.01)*rate);i<(t+.01)*rate;i++)max=Math.max(max,Math.abs(data[i]-data[i-1]));return max;};
    // Constant carrier isolates the bed duck envelope from changing tonal content.
    const dc=new OfflineAudioContext(1,3*rate,rate),gain=dc.createGain();gain.connect(dc.destination);const duck=new SceneMusic(dc,gain);
    const buffer=dc.createBuffer(1,rate,rate);buffer.getChannelData(0).fill(.1);
    duck.select({id:'test',clips:[{bed:{...script.scenes[ids[0]].beds[0],loop:[0,1],fade_seconds:.05,gain_db:-20,duck_db:-8},buffer}]},0,false,true);
    duck.play({timeline:[{type:'line',t:1,dur:.5,audio:'test',text:'test'}]}, {},0);
    const d=(await dc.startRendering()).getChannelData(0),mean=(a,b)=>{let sum=0;for(let i=Math.floor(a*rate);i<Math.floor(b*rate);i++)sum+=Math.abs(d[i]);return sum/(Math.floor(b*rate)-Math.floor(a*rate));};
    const bytes=new Uint8Array(data.buffer);let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));
    return {pcmBase64:btoa(binary),sampleRate:rate,renderSeconds:18,sfxClips:4,peak,peakDb:20*Math.log10(peak),maxSampleDelta:maxDelta,maxDeltaTime,fadeBoundaryDelta:Math.max(...[13,14,14.5,15,15.1,15.2,16,16.05].map(seam)),loopSeamDelta:seam(12.02),pauseRms:rms(14.1,14.4),audibleRms:rms(1,2),maxSources,
      duckMeasuredDb:20*Math.log10(mean(1.15,1.4)/mean(.5,.8)),duckRestoredDb:20*Math.log10(mean(2,2.3)/mean(.5,.8)),canonicalSecondOffset:canonicalSceneOffset(script,1)};
  },{script,assetBase:base+info.asset_base});
  const pcm=Buffer.from(result.mix.pcmBase64,'base64');delete result.mix.pcmBase64;
  const header=Buffer.alloc(44);header.write('RIFF');header.writeUInt32LE(36+pcm.length,4);header.write('WAVEfmt ',8);header.writeUInt32LE(16,16);header.writeUInt16LE(3,20);header.writeUInt16LE(1,22);header.writeUInt32LE(result.mix.sampleRate,24);header.writeUInt32LE(result.mix.sampleRate*4,28);header.writeUInt16LE(4,32);header.writeUInt16LE(32,34);header.write('data',36);header.writeUInt32LE(pcm.length,40);
  await fs.writeFile(path.join(project,'reports/M3d3-mix-private.wav'),Buffer.concat([header,pcm]));
  console.log('Measured native graph:',result.mix);
  assert.ok(result.mix.peak<.95);assert.equal(result.mix.pauseRms,0);assert.ok(result.mix.audibleRms>.0001);assert.ok(Math.abs(result.mix.duckMeasuredDb+8)<.05);assert.ok(Math.abs(result.mix.duckRestoredDb)<.05);
  assert.ok(result.mix.fadeBoundaryDelta<.005);assert.ok(result.mix.loopSeamDelta<.005);assert.deepEqual(errors,[]);result.pageErrors=errors;result.browser=context.browser().version();
  await fs.writeFile(path.join(project,'reports/M3d3-browser.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
}catch(e){console.error(e);try{const d=await diag();delete d.frameTimes;delete d.visualClockSampleErrorMs;console.error('Last reader diagnostics:',d);}catch{}throw e;}finally{await context.close();}
