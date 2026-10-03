import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m1g-'+process.pid),{channel:'msedge',headless:true,
 viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
try{
 const info=await (await context.request.get(base+'/api/chapters/golden-m1d/chapter/playback')).json();
 const full=await (await context.request.get(base+info.script_url)).json();let available=1,failed=false;
 await page.route('**/api/chapters/golden-m1d/chapter/playback',r=>r.fulfill({json:{...info,script_url:`/stream-test-${available}/motionscript.json`,partial:available<5,total_pages:5,processing_status:failed?'failed':'running',processing_error:failed?'OCR fixture interrupted':null}}));
 await page.route('**/stream-test-*/motionscript.json',r=>r.fulfill({json:{...full,pages:full.pages.slice(0,Number(r.request().url().match(/stream-test-(\d+)/)[1]))}}));
 await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();
 assert.equal((await diag()).pages,1);assert.equal(await page.locator('#depth').isDisabled(),true);await page.locator('#mode').selectOption('tap');await page.locator('#stage').click({position:{x:20,y:40}});
 await page.waitForFunction(()=>window.mangaMotionDiagnostics.index===1);const before=await diag();
 failed=true;await page.waitForFunction(()=>document.getElementById('error').textContent.includes('OCR fixture interrupted'));
 available=3;failed=false;await page.waitForFunction(()=>window.mangaMotionDiagnostics.pages===3);
 const appended=await diag();assert.equal(appended.index,before.index);assert.equal(appended.switches,before.switches);assert.ok(appended.time>=before.time);
 available=5;await page.waitForFunction(()=>window.mangaMotionDiagnostics.pages===5&&!window.mangaMotionDiagnostics.partial);
 assert.equal(await page.locator('#depth').isDisabled(),false);assert.equal((await diag()).depth,true);
 for(let i=2;i<25;i++){await page.locator('#stage').click({position:{x:20,y:40}});await ready();await page.waitForFunction(i=>window.mangaMotionDiagnostics.index===i,i);}
 assert.deepEqual(errors,[]);assert.deepEqual((await diag()).errors,[]);
 const result={firstPages:1,appendedPages:[3,5],preservedIndex:before.index,preservedSwitches:before.switches,finalPanels:(await diag()).panels,errors,browser:context.browser().version()};
 await fs.writeFile(path.join(root,'reports/M1g-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await context.close();}
