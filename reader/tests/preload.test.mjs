import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import ts from 'typescript';
const source=await fs.readFile(path.join(import.meta.dirname,'../src/preload.ts'),'utf8');
const {WindowPrefetch,pageWindow}=await import('data:text/javascript;base64,'+Buffer.from(ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText).toString('base64'));
const flush=()=>new Promise(r=>setTimeout(r,10));
test('prefetch shares acquisition, discards stale completion and releases the previous window',async()=>{
 let finish,calls=[],released=[];
 const cache=new WindowPrefetch(async key=>{calls.push(key);if(key==='a')await new Promise(r=>finish=r);return {key};},async key=>released.push(key));
 cache.select(['a','b']);await flush();const current=cache.acquire('a',false);cache.select(['c','d']);finish();await current;await flush();
 assert.deepEqual(calls,['a','c','d']);assert.deepEqual([...cache.cache.keys()],['c','d']);assert.deepEqual(released,['a']);
 cache.select(['e'],['c']);await flush();assert.deepEqual([...cache.cache.keys()],['c','e']);await cache.close();assert.equal(cache.cache.size,0);
});
test('page window caps at ±2 and respects aggregate pixel memory while retaining current page',()=>{
 const pages=Array.from({length:10},()=>({size:[1000,1000]}));assert.deepEqual(pageWindow(pages,5),[5,6,4,7,3]);assert.deepEqual(pageWindow(pages,0),[0,1,2]);
 assert.deepEqual(pageWindow(pages,5,2_000_000),[5,6]);pages[5].size=[9000,9000];assert.deepEqual(pageWindow(pages,5),[5]);
});
test('current acquisition stays pinned while stale speculative work completes',async()=>{
 let finish;const released=[];
 const cache=new WindowPrefetch(async key=>{if(key==='old')await new Promise(r=>finish=r);return key;},async key=>released.push(key));
 cache.select(['old']);await flush();await cache.acquire('current');finish();await flush();assert.equal(cache.cache.has('current'),true);assert.ok(!released.includes('current'));
 cache.select(['current']);await flush();await cache.close();
});
