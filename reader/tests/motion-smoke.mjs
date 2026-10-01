import {chromium} from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const browser=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m3b-'+process.pid),{channel:'msedge',headless:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
try{
 await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#mode').selectOption('tap');
 await page.locator('#play').click();await page.waitForTimeout(1100);
 await page.locator('#motion').selectOption('subtle');assert.equal((await diag()).motionPreset,'subtle');
 await page.locator('#motion').selectOption('hype');assert.equal((await diag()).motionPreset,'hype');
 await page.locator('#reduce').check();await page.waitForTimeout(50);const first=(await diag()).renderedRect;await page.waitForTimeout(600);assert.deepEqual((await diag()).renderedRect,first);assert.equal((await diag()).shakeActive,false);
 await page.locator('#reduce').uncheck();await page.locator('#motion').selectOption('normal');
 for(let i=1;i<25;i++){await page.locator('#next').click();await page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,i);assert.deepEqual((await diag()).errors,[]);}
 const d=await diag(),times=d.frameTimes.toSorted((a,b)=>a-b);
 assert.deepEqual(errors,[]);assert.ok(await page.evaluate(()=>document.body.scrollWidth<=390));
 const report={browser:browser.browser().version(),visited:25,motionControls:true,reduceHolds:true,errors,
 frameSamples:times.length,medianFrameMs:times[Math.floor(times.length*.5)],p95FrameMs:times[Math.floor(times.length*.95)],clockSampleProxyMs:Math.max(0,...d.visualClockSampleErrorMs),loadedTextures:d.loadedTextures};
 await fs.writeFile(path.join(root,'reports/M3b-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
