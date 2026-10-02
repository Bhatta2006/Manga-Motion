import {chromium} from 'playwright-core';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs/promises';import path from 'node:path';import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME,base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const script=JSON.parse(await fs.readFile(path.join(root,'library/golden-m1d/chapter/motionscript.json'),'utf8'));
const panels=script.pages.flatMap(p=>p.panels),indices=panels.flatMap((p,i)=>p.timeline.some(e=>e.type==='sfx')?[i]:[]);
const browser=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m3c-'+process.pid),{channel:'msedge',headless:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
try{
 await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#mode').selectOption('tap');
 assert.equal(await page.locator('#sfx').isDisabled(),false);
 const heard=[];
 for(let i=0;i<panels.length;i++){
  if(i){await page.locator('#next').click();await page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,i);}
  if(indices.includes(i)){
   if(!i)await page.locator('#play').click();
   await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxRms>1e-5,null,{timeout:4000});heard.push(i);
  }
 }
 assert.deepEqual(heard,indices);
 await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#mode').selectOption('tap');
 await page.locator('#sfx').uncheck();await page.locator('#play').click();await page.waitForTimeout(650);assert.equal((await diag()).sfxRms,0);
 await page.locator('#sfx').check();await page.locator('#replay').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxRms>1e-5);
 await page.locator('#play').click();await page.waitForTimeout(80);assert.equal((await diag()).playing,false);assert.ok((await diag()).sfxRms<1e-6);
 const samples=JSON.parse(execFileSync(path.join(root,'.venv/Scripts/python.exe'),['-m','pipeline.audio.evaluate','--series','golden-m1d','--chapter','chapter'],{cwd:root,encoding:'utf8'})).samples;
 assert.equal(samples.length,3);
 for(const sample of samples){
  await page.goto(base+sample.url);await ready();
  assert.equal((await diag()).panels,panels.length);
  assert.equal(await page.locator('#caption').isVisible(),false);
  assert.equal(await page.locator('#speed-wrap').isVisible(),false);
  assert.equal(await page.locator('#sfx').isDisabled(),false);
  await page.locator('#mode').selectOption('tap');await page.locator('#play').click();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxRms>1e-5);
 }
 await page.route('**/assets/sfx/*',route=>route.fulfill({status:404,body:'missing test sound'}));
 await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();assert.match(await page.locator('#error').textContent(),/Audio unavailable/);
 await page.locator('#play').click();await page.waitForTimeout(300);assert.equal((await diag()).playing,true);
 assert.deepEqual(errors,[]);
 const result={heardPanels:heard,muteSilent:true,pauseStops:true,comparisonSnapshots:samples.length,comparisonLabelsHidden:true,comparisonAudioWorks:true,missingAssetVisible:true,silentFallbackClock:true,errors,browser:browser.browser().version()};
 await fs.writeFile(path.join(root,'reports/M3c-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
