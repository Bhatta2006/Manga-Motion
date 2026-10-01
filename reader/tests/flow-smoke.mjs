import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m1f-'+process.pid),{channel:'msedge',headless:true,
  viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const at=i=>page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,i);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const result={};
async function wheel(delta){await page.locator('.flow-rail').hover();await page.mouse.wheel(0,delta);}
try{
  for(const direction of ['rtl','ltr']){
    if(direction==='ltr')await page.route('**/motionscript.json',async r=>{const response=await r.fetch();const data=await response.json();data.direction='ltr';await r.fulfill({json:data});});
    await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();
    assert.equal(await page.locator('#mode').inputValue(),'flow');
    const height=await page.locator('.flow-rail').evaluate(e=>e.clientHeight);
    const visited=[0];
    for(let i=1;i<25;i++){await wheel(height*1.1);await at(i);visited.push(i);}
    const end=await diag(),times=end.frameTimes.toSorted((a,b)=>a-b);result[direction]={visited,transportClicks:0,maxTextures:end.loadedTextures,
      medianFrameMs:times[Math.floor(times.length*.5)],p95FrameMs:times[Math.floor(times.length*.95)],clockProxyMs:Math.max(0,...end.visualClockSampleErrorMs)};
    await wheel(-height*1.1);await at(23);
    const switches=(await diag()).switches;
    await wheel(5);await page.waitForTimeout(500);assert.equal((await diag()).index,23);assert.equal((await diag()).switches,switches);
    await wheel(-height*12);await at(22);await page.waitForTimeout(400);assert.equal((await diag()).index,22);
    await page.unroute('**/motionscript.json');
  }
  await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();
  await page.locator('.flow-rail').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.playing);
  await page.locator('.flow-rail').click();assert.equal((await diag()).playing,false);
  await page.locator('#mode').selectOption('auto');await page.waitForFunction(()=>window.mangaMotionDiagnostics.playing&&window.mangaMotionDiagnostics.auto);
  await wheel(0);await page.waitForTimeout(300);
  assert.equal(await page.locator('#mode').inputValue(),'flow');assert.equal((await diag()).auto,false);assert.equal((await diag()).playing,false);
  await page.locator('#classic').click();assert.equal((await diag()).classic,true);assert.equal(await page.locator('.flow-rail').isVisible(),false);
  await page.locator('#classic').click();assert.equal(await page.locator('.flow-rail').isVisible(),true);
  assert.deepEqual(errors,[]);assert.deepEqual((await diag()).errors,[]);
  result.handoff='tap pause/resume, manual interruption of Auto, original context verified';
  result.browser=context.browser().version();result.bodyWidth=await page.evaluate(()=>document.body.scrollWidth);assert.ok(result.bodyWidth<=390);
  await fs.writeFile(path.join(root,'reports/M1f-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await context.close();}
