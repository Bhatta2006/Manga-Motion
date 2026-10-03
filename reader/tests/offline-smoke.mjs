import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m5a-'+process.pid),{channel:'msedge',headless:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[],result={};page.on('pageerror',e=>errors.push(String(e)));
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const url=base+'/?series=golden-m1d&chapter=chapter&offline=enabled';
try{
 const start=performance.now();await page.goto(url);await ready();result.onlineFirstReadyMs=performance.now()-start;
 await page.waitForFunction(()=>navigator.serviceWorker.controller);
 await page.waitForFunction(()=>window.mangaMotionDiagnostics.loadedTextures>=3);
 const saving=performance.now();await page.locator('#offline-save').click();await page.waitForFunction(()=>document.getElementById('offline-status').textContent.startsWith('Saved offline'));
 result.saveSeconds=(performance.now()-saving)/1000;
 result.saved=await page.evaluate(async()=>{const cache=await caches.open('mm-offline-index-v1');return (await (await cache.match((await cache.keys())[0])).json());});
 assert.ok(result.saved.bytes>0);const firstCache=result.saved.cacheName;
 const info=await (await context.request.get(base+'/api/chapters/golden-m1d/chapter/playback')).json(),script=await (await context.request.get(base+info.script_url)).json(),panels=script.pages.flatMap(p=>p.panels);
 const layerIndex=panels.findIndex(p=>p.layers?.length),soundIndex=panels.findIndex((p,i)=>i>0&&p.timeline.some(e=>e.type==='sfx'));assert.ok(layerIndex>=0&&soundIndex>=0);
 // Force a second save failure before commit; old complete cache must survive.
 await context.route('**/playback/*/manifest',r=>r.fulfill({status:503}));await page.locator('#offline-save').click();await page.waitForFunction(()=>document.getElementById('offline-status').textContent.includes('manifest unavailable'));await context.unroute('**/playback/*/manifest');
 assert.equal(await page.evaluate(()=>caches.has('mm-offline-index-v1')),true);assert.equal(await page.evaluate(key=>caches.has(key),firstCache),true);
 await context.route('**/playback/*/manifest',async r=>{const response=await r.fetch(),data=await response.json();data.assets[Object.keys(data.assets)[0]]='0'.repeat(64);await r.fulfill({json:data});});
 await page.locator('#offline-save').click();await page.waitForFunction(()=>document.getElementById('offline-status').textContent.includes('hash mismatch'));await context.unroute('**/playback/*/manifest');
 assert.deepEqual(await page.evaluate(async()=>{const cache=await caches.open('mm-offline-index-v1');const record=await (await cache.match((await cache.keys())[0])).json();return {name:record.cacheName,caches:(await caches.keys()).filter(k=>k.startsWith('mm-chapter-'))};}),{name:firstCache,caches:[firstCache]});
 result.recovery='503 manifest and failed asset SHA retain the previous complete copy; incomplete staging removed';
 await context.setOffline(true);const reopening=performance.now();await page.reload();await ready();result.offlineFirstReadyMs=performance.now()-reopening;assert.equal((await diag()).offline,true);assert.equal(await page.locator('#speed').isDisabled(),true);
 await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.musicRms>0&&window.mangaMotionDiagnostics.ambienceRms>0);await page.locator('#play').click();result.offlineMusicAndAmbience=true;
 let maxTextures=0,maxAudioBytes=0;const switches=[];
 for(let i=0;i<25;i++){
   if(i){const next=performance.now();await page.locator('#next').click();await ready();await page.waitForFunction(i=>window.mangaMotionDiagnostics.index===i,i);switches.push(performance.now()-next);}
   const state=await diag();maxTextures=Math.max(maxTextures,state.loadedTextures);maxAudioBytes=Math.max(maxAudioBytes,state.prefetchedAudioBytes??0);assert.deepEqual(state.errors,[]);assert.equal(await page.locator('#error').textContent(),'');
   if(i===soundIndex){assert.ok(state.decodedCurrentClips>0);if(!(await diag()).playing)await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.sfxRms>0);await page.locator('#play').click();result.offlineSfx=true;}
   if(i===layerIndex){assert.equal(state.characterLayers,1);result.offlineLayer=true;}
 }
 assert.ok(maxTextures<=6);assert.ok(maxAudioBytes<=32*2**20);result.maxTextures=maxTextures;result.maxAudioBytes=maxAudioBytes;
 switches.sort((a,b)=>a-b);result.navigationMedianMs=switches[Math.floor(switches.length*.5)];result.navigationP95Ms=switches[Math.floor(switches.length*.95)];result.jsHeapBytes=await page.evaluate(()=>performance.memory?.usedJSHeapSize??null);
 await page.goto(base+'/');await page.locator('.read-link').waitFor();assert.match(await page.locator('#library-error').textContent(),/Offline/);assert.equal(await page.locator('#import-submit').isDisabled(),true);assert.equal(await page.locator('.chapter-card').count(),1);
 await page.locator('.read-link').click();await ready();await page.locator('#offline-remove').click();await page.waitForFunction(()=>document.getElementById('offline-remove').hidden);assert.equal(await page.evaluate(key=>caches.has(key),firstCache),false);
 await context.setOffline(false);assert.deepEqual(errors,[]);result.pageErrors=errors;result.browser=context.browser().version();delete result.saved.info;result.saved.cacheName='private browser chapter cache';
 await fs.writeFile(path.join(root,'reports/M5a-browser.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
}catch(e){console.error('Offline smoke state',await page.locator('#offline-status').textContent().catch(()=>''),await diag().catch(()=>({})));throw e;}finally{await context.close();}
