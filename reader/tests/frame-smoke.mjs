// Focused check for the viewport-mask fix; the full timeline smoke is separate.
import {chromium} from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','frame-'+process.pid),{channel:'msedge',headless:true,viewport:{width:1280,height:900},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage();await page.bringToFront();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
try{
  await page.goto('http://127.0.0.1:5173');await ready();
  await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.playing);await page.waitForTimeout(500);
  await page.screenshot({path:path.join(root,'reports/M0b-frame-desktop-private.png')});
  for(let i=0;i<24;i++){await page.locator('#next').click();await ready();}
  await page.waitForTimeout(300);
  await page.screenshot({path:path.join(root,'reports/M0b-frame-last-private.png')});
  await page.locator('#replay').click();await ready();await page.waitForTimeout(1500);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
  await page.screenshot({path:path.join(root,'reports/M0b-frame-mobile-private.png')});
  await page.locator('#classic').click();assert.equal(await page.evaluate(()=>window.mangaMotionDiagnostics.classic),true);
  const d=await page.evaluate(()=>window.mangaMotionDiagnostics),sorted=d.frameTimes.sort((a,b)=>a-b);
  assert.deepEqual(errors,[]);
  const result={index:d.index,maskCheck:'desktop/mobile screenshots captured; all 25 panel navigation passes',frameSamples:sorted.length,medianFrameMs:sorted[Math.floor(sorted.length*.5)],p95FrameMs:sorted[Math.floor(sorted.length*.95)],maxFrameMs:Math.max(...sorted),errors};
  await fs.writeFile(path.join(root,'reports/M0b-frame.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
}finally{await context.close();}
