// Full chapter navigation and actual failed-import retry through the local service.
import {chromium} from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const project=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m1d-'+process.pid),{
  channel:'msedge',headless:true,viewport:{width:1280,height:900},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const at=index=>page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,index);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const card=()=>page.locator('[data-series="golden-m1d"][data-chapter="chapter"]');
const result={};
try{
  await page.goto(base);await card().locator('a.read-link').waitFor();
  await page.screenshot({path:path.join(project,'reports/M1d-library-private.png'),fullPage:true});
  for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
    await page.setViewportSize(viewport);await page.goto(base);await card().locator('a.read-link').click();await ready();
    assert.equal((await diag()).panels,25);const visited=[];
    const chapterScript=JSON.parse(await fs.readFile(path.join(project,'library/golden-m1d/chapter/motionscript.json'),'utf8'));
    const chapterHasSfx=chapterScript.pages.some(p=>p.panels.some(q=>q.timeline.some(e=>e.type==='sfx')));
    assert.equal(await page.locator('#sfx').isDisabled(),!chapterHasSfx);
    assert.equal(await page.locator('#sfx').isChecked(),chapterHasSfx);
    assert.equal(await page.locator('#mode option[value=auto]').textContent(),'Auto');
    await page.locator('#mode').selectOption('tap');
    for(let index=0;index<25;index++){
      if(index){await page.locator('#stage').click({position:{x:15,y:40}});await ready();}
      await page.waitForFunction(i=>window.mangaMotionDiagnostics?.index===i&&window.mangaMotionDiagnostics?.renderedRect?.every(Number.isFinite),index);
      const d=await diag();assert.deepEqual(d.errors,[]);assert.ok(d.loadedTextures<=3);visited.push(index);
    }
    const d=await diag(),times=d.frameTimes.toSorted((a,b)=>a-b);
    result[viewport.width]={visited,frameSamples:times.length,medianFrameMs:times[Math.floor(times.length*.5)],p95FrameMs:times[Math.floor(times.length*.95)],
      visualClockSampleErrorMs:Math.max(0,...d.visualClockSampleErrorMs),maxLoadedTextures:d.loadedTextures,bodyWidth:await page.evaluate(()=>document.body.scrollWidth)};
    assert.ok(result[viewport.width].bodyWidth<=viewport.width);
    await page.screenshot({path:path.join(project,`reports/M1d-reader-${viewport.width}-private.png`)});
    await page.locator('.library-link').click();await card().waitFor();
  }
  await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();
  await page.locator('#mode').selectOption('tap');
  await page.locator('#stage').click();await at(1);
  await page.locator('#play').click();await page.locator('#play').blur();
  await page.keyboard.press('ArrowLeft');await at(2);
  await page.locator('#play').blur();await page.keyboard.press('ArrowRight');await at(1);
  // Hold a panel long enough to measure steady rendering rather than page-load bursts.
  await page.locator('#replay').click();await page.waitForTimeout(1700);
  const d=await diag(),times=d.frameTimes.toSorted((a,b)=>a-b);
  result.steady={frameSamples:times.length,medianFrameMs:times[Math.floor(times.length*.5)],p95FrameMs:times[Math.floor(times.length*.95)],clockProxyMs:Math.max(0,...d.visualClockSampleErrorMs)};
  await page.locator('#classic').click();assert.equal((await diag()).playing,false);assert.equal((await diag()).classic,true);
  result.rtlKeyboard='left advances, right returns';result.originalPage='pauses and remains available';
  // LTR key mapping with a test-only contract fixture; no claim of real LTR OCR quality.
  await page.route('**/motionscript.json',async route=>{const response=await route.fetch();const script=await response.json();script.direction='ltr';await route.fulfill({json:script});});
  await page.reload();await ready();await page.keyboard.press('ArrowRight');await at(1);
  await page.keyboard.press('ArrowLeft');await at(0);await page.unroute('**/motionscript.json');result.ltrKeyboard='controlled fixture passes';
  const corrupt=path.join(runtime,'tmp','m1d-retry.cbz');await fs.writeFile(corrupt,'deliberately invalid ZIP fixture');
  await page.goto(base);await page.locator('summary').click();
  await page.locator('[name=source]').fill(corrupt);await page.locator('[name=series]').fill('golden-m1d');await page.locator('[name=chapter]').fill('chapter');
  await page.locator('#import-submit').click();await page.waitForFunction(()=>document.getElementById('import-message').textContent.includes('queued.'));
  await card().getByText('Processing failed',{exact:true}).waitFor({timeout:20000});assert.ok(await card().locator('.job-error').textContent());
  assert.equal(await card().locator('a.read-link').textContent(),'Read saved version');
  await fs.copyFile(path.join(project,'library/fixtures/m1a/golden.cbz'),corrupt);
  await card().getByRole('button',{name:'Retry processing'}).click();
  await card().getByText('Ready to read',{exact:true}).waitFor({timeout:30000});result.failedImportRetry='visible failure, preserved previous playback, successful retry';
  await card().locator('a.read-link').click();await ready();assert.equal((await diag()).panels,25);
  // The original SFX preview must still work with immutable API asset URLs.
  await page.goto(base+'/?series=preview&chapter=m0b');await ready();
  assert.equal(await page.locator('#sfx').isDisabled(),false);
  const legacyInfo=await (await context.request.get(base+'/api/chapters/preview/m0b/playback')).json();
  const legacyScript=await (await context.request.get(base+legacyInfo.script_url)).json();
  const firstSfx=legacyScript.pages.flatMap(p=>p.panels).findIndex(p=>p.timeline.some(e=>e.type==='sfx'));
  assert.ok(firstSfx>=0);for(let i=1;i<=firstSfx;i++){await page.locator('#next').click();await at(i);}
  await page.locator('#replay').click();
  await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxRms>0.0001,{},{timeout:6000});
  assert.deepEqual((await diag()).errors,[]);result.legacySfx='audible Web Audio signal through the new asset base';
  await page.locator('#sfx').uncheck();await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxMuted);
  assert.deepEqual(errors,[]);result.pageErrors=errors;result.browser=context.browser().version();
  await fs.writeFile(path.join(project,'reports/M1d-browser.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
}finally{await context.close();}
