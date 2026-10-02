// Transient controlled corrections on the real golden chapter, restored exactly.
import {chromium} from 'playwright-core';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const project=path.resolve(import.meta.dirname,'../..'),runtime=process.env.MANGAMOTION_RUNTIME;
assert.ok(runtime?.toLowerCase().startsWith('d:'));
const base=process.env.MANGAMOTION_API??'http://127.0.0.1:5174',url='/api/chapters/golden-m1d/chapter/review';
const context=await chromium.launchPersistentContext(path.join(runtime,'browser-tests','m4a-'+process.pid),{channel:'msedge',headless:true,viewport:{width:390,height:844},downloadsPath:path.join(runtime,'browser-downloads'),artifactsDir:path.join(runtime,'browser-artifacts')});
const page=await context.newPage(),errors=[],result={};page.on('pageerror',e=>errors.push(String(e)));
const original=await (await context.request.get(base+url)).json();
const replacement='One two three four five six seven eight nine ten. Test '+process.pid;
try{
  await page.goto(base);await page.locator('[data-series=golden-m1d][data-chapter=chapter] .review-link').click();
  await page.locator('#fix-text').waitFor();assert.equal(await page.locator('#review-page option').count(),5);
  assert.ok(original.issues.length>53);assert.ok(await page.locator('.review-crop image').first().getAttribute('href'));
  await page.locator('#fix-text').fill(replacement);await page.locator('#fix-kind').selectOption('dialogue');await page.locator('#fix-confirm').check();
  const savedResponse=page.waitForResponse(r=>r.url()===base+url&&r.request().method()==='POST');const started=performance.now();await page.locator('#fix-save').click();const response=await savedResponse;
  assert.equal(response.status(),200);const saved=await response.json();await page.locator('#review-message').getByText('Saved.',{exact:false}).waitFor();
  result.saveWallSeconds=(performance.now()-started)/1000;result.serverSeconds=saved.elapsed_seconds;result.stageMetrics=saved.metrics;
  assert.equal(saved.metrics.stage.cache_hits,4);assert.equal(saved.metrics.sfx_stage.cache_hits,4);assert.equal(saved.metrics.music_stage.cache_hits,4);
  result.before=original.unresolved;result.after=saved.unresolved;assert.ok(saved.unresolved<original.unresolved);
  await page.reload();await page.locator('#fix-text').waitFor();assert.equal(await page.locator('#fix-text').inputValue(),replacement);
  const revertResponse=page.waitForResponse(r=>r.url()===base+url&&r.request().method()==='POST');await page.locator('#fix-revert').click();const reverted=await revertResponse;assert.equal(reverted.status(),200);
  const revertedData=await reverted.json();assert.equal(revertedData.corrections.pages[original.pages[0].page_sha256],undefined);
  await page.waitForFunction(text=>document.getElementById('fix-text').value===text,original.pages[0].texts[0].text);result.revert='Original text restored; empty geometry bindings pruned';
  await page.locator('#review-order').click();await page.getByRole('button',{name:'Move panel_000 later',exact:true}).click();const orderResponse=page.waitForResponse(r=>r.url()===base+url&&r.request().method()==='POST');await page.locator('#fix-save').click();assert.equal((await orderResponse).status(),200);await page.locator('#fix-order li span').first().getByText('panel_001',{exact:true}).waitFor();
  assert.ok(await page.evaluate(()=>document.body.scrollWidth)<=390);result.mobile='390 px: text confirmation, order buttons and no overflow';
  await page.screenshot({path:path.join(project,'reports/M4a-review-private.png'),fullPage:true});
  const current=await (await context.request.get(base+url)).json();
  const stale=await context.request.post(base+url,{data:{expected_revision:original.revision,corrections:original.corrections}});assert.equal(stale.status(),409);result.stale='Stale update rejected, saved data retained';
  await page.route('**/api/chapters/golden-m1d/chapter/review',route=>route.request().method()==='POST'?route.fulfill({status:409,json:{detail:'Controlled save failure'}}):route.continue());
  await page.locator('#fix-save').click();await page.locator('#review-message').getByText('Controlled save failure',{exact:false}).waitFor();assert.equal(await page.locator('#fix-save').isEnabled(),true);await page.unroute('**/api/chapters/golden-m1d/chapter/review');
  const unchanged=await (await context.request.get(base+url)).json();assert.deepEqual(unchanged.corrections,current.corrections);result.failure='Save failure shows error and retains editable inputs';
  assert.deepEqual(errors,[]);result.pageErrors=errors;result.browser=context.browser().version();
  await fs.writeFile(path.join(project,'reports/M4a-browser.json'),JSON.stringify(result,null,2)+'\n');
  const concise={...result};delete concise.stageMetrics;console.log(JSON.stringify(concise,null,2));
}finally{
  const latest=await (await context.request.get(base+url)).json();const restored=await context.request.post(base+url,{data:{expected_revision:latest.revision,corrections:original.corrections}});
  assert.equal(restored.status(),200,'Golden human corrections must restore');await context.close();
}
