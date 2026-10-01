// Feed compiled real chapter assets to the existing preview through a test-only route.
import {chromium} from 'playwright-core';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const project=path.resolve(import.meta.dirname,'../..');
const root=path.join(project,'library/golden-m1b/chapter');
const runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime&&path.resolve(runtime).toLowerCase().startsWith('d:'));
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests',`m1c-${process.pid}`),{
  channel:'msedge',headless:true,viewport:{width:1280,height:900},
  downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')
});
const page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(String(e)));
let invalid=false;
await context.route('**/chapter/**',async route=>{
  const relative=new URL(route.request().url()).pathname.slice('/chapter/'.length);
  if(relative==='motionscript.json'){
    const script=JSON.parse(await fs.readFile(path.join(root,relative),'utf8'));
    if(invalid)script.pages[0].panels[0].timeline[0].dur=0;
    await route.fulfill({json:script});
  }else if(/^pages\/[a-f0-9]{64}\.[a-z]+$/.test(relative))await route.fulfill({path:path.join(root,relative)});
  else await route.fulfill({status:404,body:'Missing test asset'});
});
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const result={};
try{
  await page.goto('http://127.0.0.1:5173');await ready();
  assert.equal((await diag()).panels,25);
  for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
    await page.setViewportSize(viewport);await page.reload();await ready();
    const visited=[];
    for(let i=0;i<25;i++){
      if(i){await page.locator('#next').click();await ready();}
      await page.waitForFunction(expected=>window.mangaMotionDiagnostics?.index===expected&&window.mangaMotionDiagnostics?.renderedRect?.every(Number.isFinite),i);
      const d=await diag();assert.equal(d.index,i);assert.equal(d.errors.length,0);
      visited.push(i);
    }
    result[`${viewport.width}x${viewport.height}`]={visited,canvas:(await diag()).viewport,bodyWidth:await page.evaluate(()=>document.body.scrollWidth)};
    assert.ok(result[`${viewport.width}x${viewport.height}`].bodyWidth<=viewport.width);
  }
  await page.reload();await ready();await page.locator('#reduce').check();
  await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.playing);await page.waitForTimeout(100);
  const held=(await diag()).renderedRect;await page.waitForTimeout(150);
  assert.deepEqual((await diag()).renderedRect,held);result.reduceMotion='holds source camera frame';
  await page.locator('#classic').click();assert.equal((await diag()).classic,true);assert.equal((await diag()).playing,false);
  result.originalPage='accessible and pauses playback';
  await page.screenshot({path:path.join(project,'reports/M1c-mobile-private.png')});
  invalid=true;await page.reload();await page.waitForFunction(()=>document.getElementById('error')?.textContent.includes('Invalid MotionScript'));
  result.invalidContract='visible error before renderer initialization';
  result.browser=context.browser()?.version();result.pageErrors=errors;assert.deepEqual(errors,[]);
  await fs.writeFile(path.join(project,'reports/M1c-browser.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
}finally{await context.close();}
