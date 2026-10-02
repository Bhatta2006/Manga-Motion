// Serial integration on the real golden chapter. Corrections restored in finally.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174',reviewUrl='/api/chapters/golden-m1d/chapter/review';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m4b-'+process.pid),{channel:'msedge',headless:true,hasTouch:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[],result={};page.on('pageerror',e=>errors.push(String(e)));
const original=await (await context.request.get(base+reviewUrl)).json();
const diag=()=>page.evaluate(()=>window.mangaMotionDiagnostics);
const ready=()=>page.waitForFunction(()=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading);
const at=i=>page.waitForFunction(i=>window.mangaMotionDiagnostics?.ready&&!window.mangaMotionDiagnostics.loading&&window.mangaMotionDiagnostics.index===i,i);
async function hold(x,y){await page.mouse.move(x,y);await page.mouse.down();await page.waitForTimeout(570);await page.mouse.up();}
function wav(seconds){const rate=24000,n=rate*seconds,b=Buffer.alloc(44+n*2);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*2,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(n*2,40);return b;}
try{
  await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.waitForFunction(()=>window.mangaMotionDiagnostics.reviewReady);
  let box=await page.locator('#stage').boundingBox();
  await hold(box.x+3,box.y+3);assert.equal((await diag()).classic,true);assert.equal(await page.locator('.flow-rail').isVisible(),false);result.holdLatencyMs=(await diag()).lastHoldMs;
  await page.locator('#stage').click();assert.equal((await diag()).classic,false);assert.equal(await page.locator('.flow-rail').isVisible(),true);
  const d=await diag(),p=original.pages[0],text=p.texts.find(t=>t.panel_id==='panel_000');assert.ok(text);
  const [tx,ty,scale]=d.worldTransform,x=box.x+tx+(text.bbox[0]+text.bbox[2])/2*scale,y=box.y+ty+(text.bbox[1]+text.bbox[3])/2*scale;
  await hold(x,y);await page.locator('.fix-sheet[open]').waitFor();assert.equal(await page.locator('#fix-text').inputValue(),text.text);result.target=text.id;
  await page.locator('#fix-text').fill('Controlled bubble correction '+process.pid);await page.locator('#fix-kind').selectOption('dialogue');await page.locator('#fix-confirm').check();
  await page.route('**/api/chapters/golden-m1d/chapter/review',route=>route.request().method()==='POST'?route.fulfill({status:409,json:{detail:'Controlled conflict'}}):route.continue());
  await page.locator('#fix-save').click();await page.locator('#fix-message').getByText('Controlled conflict',{exact:false}).waitFor();assert.equal(await page.locator('#fix-text').inputValue(),'Controlled bubble correction '+process.pid);assert.equal(await page.locator('#fix-save').isEnabled(),true);await page.unroute('**/api/chapters/golden-m1d/chapter/review');
  let savedMetrics=null;await page.route('**/api/chapters/golden-m1d/chapter/review',async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();savedMetrics=(await response.json()).metrics;await route.fulfill({response});});
  const started=performance.now();await page.locator('#fix-save').click();await page.waitForURL('**&at=*');await ready();assert.equal((await diag()).index,0);assert.ok(page.url().includes('at=p0001_panel_000'));result.correctionWallSeconds=(performance.now()-started)/1000;result.metrics=savedMetrics;await page.unroute('**/api/chapters/golden-m1d/chapter/review');
  const saved=await (await context.request.get(base+reviewUrl)).json();assert.equal(saved.pages[0].texts.find(t=>t.id===text.id).text,'Controlled bubble correction '+process.pid);
  // Both simultaneous touch contacts trigger replay, never a Flow advance.
  await page.locator('#play').click();await page.waitForTimeout(400);const before=(await diag()).switches;
  box=await page.locator('#stage').boundingBox();const cdp=await context.newCDPSession(page),points=[{x:box.x+100,y:box.y+100},{x:box.x+180,y:box.y+100}];
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points});await page.waitForTimeout(80);await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await page.waitForFunction(before=>window.mangaMotionDiagnostics.switches>before,before);assert.equal((await diag()).index,0);assert.ok((await diag()).time<.8);result.replay='Two-contact CDP touch: same panel restarted';
  for(const direction of ['rtl','ltr']){
    await page.route('**/motionscript.json',async route=>{const response=await route.fetch(),data=await response.json();data.direction=direction;await route.fulfill({json:data});});
    await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#mode').selectOption('tap');
    box=await page.locator('#stage').boundingBox();await page.locator('#stage').click({position:{x:direction==='rtl'?15:box.width-15,y:35}});await at(1);
    await page.locator('#stage').click();await page.waitForFunction(()=>!window.mangaMotionDiagnostics.playing);assert.equal((await diag()).index,1);assert.equal((await diag()).time,(await diag()).duration);
    await page.locator('#stage').click();await at(2);await page.unroute('**/motionscript.json');
  }
  result.taps='RTL/LTR side navigation; playing center tap finishes, following tap advances';
  // A line fixture reuses original art and bubble bounds; deliberately mismatched
  // declared/decoded duration proves the overlay follows audio, not metadata.
  await page.route('**/audio/m4b-test.wav',route=>route.fulfill({contentType:'audio/wav',body:wav(2)}));
  await page.route('**/motionscript.json',async route=>{const response=await route.fetch(),data=await response.json(),panel=data.pages[0].panels[0],focus=panel.director.focus.find(f=>f.kind==='bubble');assert.ok(focus);data.characters.test={name:'Test',voice:'test'};panel.timeline.push({type:'line',t:.1,bubble:focus.ref,speaker:'test',text:'Clock fixture',audio:'audio/m4b-test.wav',dur:.2,emotion:{delivery:'speak',intensity:0},highlight:true});panel.timeline.sort((a,b)=>a.t-b.t);await route.fulfill({json:data});});
  await page.goto(base+'/?series=golden-m1d&chapter=chapter');await ready();await page.locator('#reduce').check();await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.glowingBubble);
  const glow=await diag();result.glowObservedClockSeconds=glow.time;result.jsHeapBytes=await page.evaluate(()=>performance.memory?.usedJSHeapSize??null);assert.equal(glow.glowAlpha,1);await page.waitForTimeout(500);assert.ok((await diag()).glowingBubble);await page.locator('#play').click();const frozen=await diag();await page.waitForTimeout(150);assert.equal((await diag()).glowingBubble,frozen.glowingBubble);assert.equal((await diag()).time,frozen.time);
  await page.locator('#play').click();await page.waitForFunction(()=>window.mangaMotionDiagnostics.time>2.15);assert.equal((await diag()).glowingBubble,null);
  result.glow='Decoded 2 s line vs 0.2 s metadata: clock-aligned highlight, pause freeze, static Reduce motion';
  // Hash originals directly before/after; overlay has no texture write path.
  const files=await fs.readdir(path.join(root,'library/golden-m1d/chapter/pages'));
  result.sourceHashes=[];for(const p of original.pages){const name=files.find(f=>f.startsWith(p.page_sha256)),bytes=await fs.readFile(path.join(root,'library/golden-m1d/chapter/pages',name));const digest=crypto.createHash('sha256').update(bytes).digest('hex');assert.equal(digest,p.page_sha256);result.sourceHashes.push(digest);}
  assert.ok(await page.evaluate(()=>document.body.scrollWidth)<=390);assert.deepEqual(errors,[]);assert.deepEqual((await diag()).errors,[]);result.pageErrors=errors;result.browser=context.browser().version();
  await page.screenshot({path:path.join(root,'reports/M4b-glow-private.png')});await fs.writeFile(path.join(root,'reports/M4b-browser.json'),JSON.stringify(result,null,2)+'\n');const summary={...result};delete summary.metrics;console.log(JSON.stringify(summary,null,2));
}finally{const latest=await (await context.request.get(base+reviewUrl)).json();const restored=await context.request.post(base+reviewUrl,{data:{expected_revision:latest.revision,corrections:original.corrections}});assert.equal(restored.status(),200);await context.close();}
