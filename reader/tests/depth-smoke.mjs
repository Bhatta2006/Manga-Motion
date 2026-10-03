import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174',url=base+'/?series=golden-m1d&chapter=chapter&at=p0005_panel_000';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m4c2-'+process.pid),{channel:'msedge',headless:true,viewport:{width:1280,height:900},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[],result={};page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const shot=name=>page.locator('canvas').screenshot({path:path.join(root,`reports/M4c2-${name}-private.png`)});
try{
  await page.goto(url);await ready();await page.waitForFunction(()=>window.mangaMotionDiagnostics.characterLayers===1);
  assert.equal((await diag()).layerPoses[0].scale,1);result.initial=await diag();delete result.initial.frameTimes;delete result.initial.visualClockSampleErrorMs;
  await shot('initial-depth');await page.locator('#depth').uncheck();await page.waitForTimeout(30);await shot('initial-flat');await page.locator('#depth').check();
  await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.layerPoses[0]?.scale>=1.0349);await page.locator('#play').click();
  const paused=await diag();assert.equal(paused.characterLayerVisible,true);await page.waitForTimeout(100);assert.deepEqual((await diag()).layerPoses,paused.layerPoses);assert.equal((await diag()).time,paused.time);
  await shot('posed-depth');await page.locator('#depth').uncheck();await page.waitForTimeout(30);await shot('posed-flat');assert.equal((await diag()).characterLayerVisible,false);
  result.pose=paused.layerPoses;result.worldTransform=paused.worldTransform;result.viewport=paused.viewport;
  const info=await (await context.request.get(base+'/api/chapters/golden-m1d/chapter/playback')).json(),script=await (await context.request.get(base+info.script_url)).json(),panel=script.pages.at(-1).panels[0];result.protectedText=panel.director.focus.filter(f=>f.kind==='bubble').map(f=>f.bbox);result.sourceBBox=panel.layers[0].source_bbox;
  const frames=paused.frameTimes.toSorted((a,b)=>a-b);result.frames={samples:frames.length,medianMs:frames[Math.floor(frames.length*.5)],p95Ms:frames[Math.floor(frames.length*.95)]};result.jsHeapBytes=await page.evaluate(()=>performance.memory?.usedJSHeapSize??null);
  await page.locator('#depth').check();await page.locator('#reduce').check();await page.waitForTimeout(30);assert.equal((await diag()).characterLayerVisible,false);
  await page.locator('#reduce').uncheck();await page.locator('#classic').click();assert.equal((await diag()).characterLayerVisible,false);await page.locator('#classic').click();
  await page.locator('#next').click();await ready();await page.waitForFunction(()=>window.mangaMotionDiagnostics.characterLayers===0);assert.equal((await diag()).characterLayerVisible,false);result.release='Mask released on next panel; pause, Reduce motion, depth toggle and overview verified';
  await page.setViewportSize({width:390,height:844});await page.goto(url);await ready();assert.equal((await diag()).characterLayers,1);assert.ok(await page.evaluate(()=>document.body.scrollWidth)<=390);
  await page.route('**/layers/*',route=>route.fulfill({status:404}));await page.reload();await ready();assert.equal((await diag()).characterLayers,0);assert.match(await page.locator('#error').textContent(),/mask unavailable/i);await page.unroute('**/layers/*');result.missing='404 mask disables only depth and warns';
  await page.route('**/layers/*',async route=>{const response=await route.fetch(),body=Buffer.from(await response.body());body[body.length-1]^=1;await route.fulfill({contentType:'image/png',body});});await page.reload();await ready();assert.equal((await diag()).characterLayers,0);assert.match(await page.locator('#error').textContent(),/hash mismatch/i);await page.unroute('**/layers/*');result.corrupt='Corrupt bytes disable only depth and warn';
  assert.deepEqual(errors,[]);assert.deepEqual((await diag()).errors,[]);result.pageErrors=errors;result.browser=context.browser().version();
  result.sourceHashes=[];const files=await fs.readdir(path.join(root,'library/golden-m1d/chapter/pages'));for(const p of script.pages){const bytes=await fs.readFile(path.join(root,'library/golden-m1d/chapter',p.image));const digest=crypto.createHash('sha256').update(bytes).digest('hex');assert.equal(digest,path.basename(p.image,'.jpg'));result.sourceHashes.push(digest);}
  await fs.writeFile(path.join(root,'reports/M4c2-browser.json'),JSON.stringify(result,null,2)+'\n');const summary={...result};delete summary.initial;console.log(JSON.stringify(summary,null,2));
}finally{await context.close();}
