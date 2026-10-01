import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m1e-'+process.pid),{
  channel:'msedge',headless:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const result={};
try{
  await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();
  assert.equal(await page.locator('#mode option[value=auto]').textContent(),'Auto');
  const initial=(await diag()).duration;
  for(const rate of ['160','320','240']){
    const response=page.waitForResponse(r=>r.url().endsWith('/pacing')&&r.request().method()==='POST');
    await page.locator('#speed').selectOption(rate);assert.equal((await response).status(),200);
    await page.waitForFunction(()=>!document.getElementById('speed').disabled);await ready();
    result[rate]=(await diag()).duration;
    assert.equal((await diag()).index,0);assert.equal((await diag()).playing,false);
  }
  assert.ok(result['160']>result['240']&&result['240']>result['320']);assert.equal(result['240'],initial);
  await page.locator('#mode').selectOption('auto');
  await page.waitForTimeout(2200);const hold=await diag();assert.equal(hold.index,0);assert.ok(hold.time>2);assert.ok(hold.time<hold.duration);
  await page.locator('#play').click();const paused=(await diag()).time;await page.waitForTimeout(250);
  assert.equal((await diag()).time,paused);await page.locator('#play').click();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.index===1,{},{timeout:10000});
  result.auto='audio-clock dwell, pause/resume and automatic advance verified';
  result.holdSeconds=hold.time;result.bodyWidth=await page.evaluate(()=>document.body.scrollWidth);
  assert.ok(result.bodyWidth<=390);assert.deepEqual(errors,[]);assert.deepEqual((await diag()).errors,[]);
  await page.locator('#play').click();await page.screenshot({path:path.join(root,'reports/M1e-reader-private.png')});
  result.browser=context.browser().version();result.errors=errors;
  await fs.writeFile(path.join(root,'reports/M1e-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await context.close();}
