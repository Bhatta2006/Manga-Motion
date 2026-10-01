import {chromium} from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const project=path.resolve(import.meta.dirname,'../..');
const runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime&&path.resolve(runtime).toLowerCase().startsWith('d:'));
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests',String(process.pid)),{
  channel:'msedge',headless:true,viewport:{width:1280,height:900},
  downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')
});
const page=await context.newPage();
await page.bringToFront();
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const results={};
try{
  await page.goto('http://127.0.0.1:5173');await ready();
  assert.equal((await diag()).panels,25);results.initial=await diag();
  await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.playing);await page.waitForTimeout(450);
  assert.ok((await diag()).playing);assert.ok((await diag()).time>0);
  await page.locator('#play').click();const paused=(await diag()).time;
  await page.waitForTimeout(250);assert.equal((await diag()).time,paused);results.pause='clock freezes';
  await page.locator('#play').click();await page.waitForTimeout(200);assert.ok((await diag()).time>paused);
  await page.locator('#replay').click();await ready();assert.ok((await diag()).time<.2);results.replay='restarts panel';
  await page.locator('#classic').click();assert.equal((await diag()).classic,true);assert.equal((await diag()).playing,false);
  await page.screenshot({path:path.join(project,'reports/M0b-classic-private.png')});
  await page.locator('#classic').click();assert.equal((await diag()).classic,false);
  const visited=[0];
  for(let i=1;i<25;i++){
    await page.locator('#stage').click();await ready();assert.equal((await diag()).index,i);visited.push(i);
  }
  results.tapVisited=visited;
  assert.ok((await diag()).loadedTextures<=3);results.textureCount=(await diag()).loadedTextures;
  await page.locator('#reduce').check();assert.equal((await diag()).reduce,true);
  const muteStarted=Date.now();
  await page.locator('#sfx').uncheck();await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxMuted);assert.equal((await diag()).sfxMuted,true);results.muteObservedMs=Date.now()-muteStarted;
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(project,'reports/M0b-mobile-private.png')});
  results.mobile={viewport:'390x844',bodyWidth:await page.evaluate(()=>document.body.scrollWidth)};assert.ok(results.mobile.bodyWidth<=390);
  await page.setViewportSize({width:1280,height:900});
  await page.goto('http://127.0.0.1:5173');await ready();
  await page.locator('#mode').selectOption('auto');
  results.browser=context.browser()?.version();
  results.webgl=await page.evaluate(()=>{
    const canvas=document.querySelector('canvas');const gl=canvas.getContext('webgl2')||canvas.getContext('webgl');
    const ext=gl?.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl?.getParameter(gl.RENDERER);
  });
  console.log('Controls pass. Running full real-duration 25-panel auto sequence.');
  let maxRms=0;const autoVisited=new Set();
  const deadline=Date.now()+400000;
  while(Date.now()<deadline){
    const d=await diag();autoVisited.add(d.index);maxRms=Math.max(maxRms,d.sfxRms);
    if(d.index===24&&!d.playing&&d.time>=d.duration-.01)break;
    await page.waitForTimeout(100);
  }
  const finished=await diag();assert.equal(finished.index,24);assert.equal(finished.playing,false);
  assert.equal(autoVisited.size,25);assert.ok(maxRms>0);results.autoVisited=[...autoVisited];results.maxSfxDigitalRms=maxRms;
  await page.screenshot({path:path.join(project,'reports/M0b-desktop-private.png')});
  const sorted=finished.frameTimes.sort((a,b)=>a-b);
  results.playback={samples:sorted.length,medianFrameMs:sorted[Math.floor(sorted.length*.5)],p95FrameMs:sorted[Math.floor(sorted.length*.95)],maxFrameMs:Math.max(...sorted),fpsApprox:1000/sorted[Math.floor(sorted.length*.5)],maxVisualClockSampleErrorMs:Math.max(...finished.visualClockSampleErrorMs),firstReadyMs:results.initial.firstReadyMs,glides:finished.glides};
  const script=JSON.parse(await fs.readFile(path.join(project,'library/preview/m0b/motionscript.json')));
  script.pages[0].panels[0].timeline.push({t:0,type:'sfx',file:'sfx/missing.wav',gain_db:-10});
  await page.route('**/chapter/motionscript.json',route=>route.fulfill({json:script}));
  await page.goto('http://127.0.0.1:5173');await ready();
  assert.match(await page.locator('#error').textContent(),/Audio unavailable/);results.missingAudio='visibly flagged';
  assert.deepEqual(errors,[]);results.pageErrors=errors;
  await fs.writeFile(path.join(project,'reports/M0b-browser.json'),JSON.stringify(results,null,2)+'\n');
  console.log(JSON.stringify(results,null,2));
}catch(e){const {frameTimes,visualClockSampleErrorMs,...state}=await diag();console.log('Failure state:',JSON.stringify(state));console.log('HUD:',await page.locator('#error').textContent());throw e;}finally{await context.close();}
