import Ajv from 'ajv';
import schema1 from '../../schema/motionscript-v1.schema.json';
import schema2 from '../../schema/motionscript-v2.schema.json';
import {bytesHash,validateSupportedScript} from './contract-v2.js';
import type {MotionScript,Page} from './script-types';
import type {Playback,Chapter} from './api';
const INDEX='mm-offline-index-v1',PREFIX='mm-chapter-v1-',BUDGET=512*2**20,ASSET_LIMIT=32*2**20;
type Saved={series:string;chapter:string;cacheName:string;bytes:number;playbackUrl:string;info:Playback; savedAt:string};
const key=(series:string,chapter:string)=>'/__offline__/'+encodeURIComponent(series)+'/'+encodeURIComponent(chapter);
let registration:Promise<ServiceWorkerRegistration>|undefined;
export function offlineEnabled(){return new URLSearchParams(location.search).get('offline')==='enabled'||!!navigator.serviceWorker?.controller;}
export function registerOffline(){
  if(!offlineEnabled())return Promise.reject(Error('Use scripts/open-reader.ps1 to enable offline storage in the D-drive browser profile'));
  if(!('serviceWorker' in navigator)||!isSecureContext)return Promise.reject(Error('Offline reading needs a supported secure browser'));
  return registration??=navigator.serviceWorker.register('/sw.js',{scope:'/'});
}
export async function offlineChapters():Promise<Saved[]>{
  if(!('caches' in window))return [];
  if(!await caches.has(INDEX))return [];
  const cache=await caches.open(INDEX),records:Saved[]=[];
  for(const request of await cache.keys()){const response=await cache.match(request);if(response){const record=await response.json();if(await caches.has(record.cacheName))records.push(record);}}
  return records;
}
export async function offlineLibrary(){
  const chapters:Chapter[]=(await offlineChapters()).map(r=>({series:r.series,chapter:r.chapter,pages:r.info.pages,playable:true,status:'completed',job:null,review_flags:0}));
  return {chapters,worker_error:null,offline:true};
}
export async function savedPlayback(series:string,chapter:string){
  const record=(await offlineChapters()).find(r=>r.series===series&&r.chapter===chapter);
  if(!record)throw Error('This chapter has not been saved for offline reading');
  return {...record.info,offline:true};
}
async function limitedBytes(response:Response){
  if(!response.ok)throw Error(`Offline asset unavailable (${response.status})`);
  const reader=response.body?.getReader();if(!reader)throw Error('Offline asset has no body');
  const chunks:Uint8Array[]=[];let size=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>ASSET_LIMIT)throw Error('Offline asset exceeds 32 MiB');chunks.push(value);}}
  catch(e){await reader.cancel();throw e;}
  const bytes=new Uint8Array(size);let cursor=0;for(const chunk of chunks){bytes.set(chunk,cursor);cursor+=chunk.length;}return bytes;
}
export function chapterAssets(script:MotionScript){
  const values=new Set<string>();
  for(const p of script.pages as Page[]){values.add(p.image);for(const q of p.panels){for(const layer of q.layers??[])values.add(layer.mask);for(const e of q.timeline)if(e.type==='sfx')values.add(e.file);else if(e.type==='line')values.add(e.audio);}}
  if(script.version===2)for(const s of Object.values(script.scenes))for(const bed of s.beds)values.add(bed.file);
  return [...values].sort();
}
export async function saveChapter(series:string,chapter:string,onProgress:(done:number,total:number)=>void=()=>{}){
  if(!navigator.locks)throw Error('Offline saves need browser storage locks');
  await registerOffline();
  await new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Offline reader installation failed; retry online')),15000);void navigator.serviceWorker.ready.then(()=>{clearTimeout(timer);resolve();},e=>{clearTimeout(timer);reject(e);});});
  return navigator.locks.request('mm-offline-write',async()=>{
    const playbackUrl=`/api/chapters/${encodeURIComponent(series)}/${encodeURIComponent(chapter)}/playback`;
    const live=await fetch(playbackUrl,{cache:'no-store'});if(!live.ok)throw Error('Chapter is unavailable');const info:Playback=await live.json();
    if(info.partial)throw Error('Wait for the complete chapter before saving offline');
    const base=playbackUrl+'/'+info.snapshot;
    if(!/^[a-f0-9]{64}$/.test(info.snapshot)||info.script_url!==base+'/motionscript.json'||info.asset_base!==base+'/assets/')throw Error('Invalid offline playback paths');
    const response=await fetch(info.script_url);const scriptBytes=await limitedBytes(response);
    const ajv=new Ajv({allErrors:true});const script=await validateSupportedScript(JSON.parse(new TextDecoder().decode(scriptBytes)),{1:ajv.compile(schema1),2:ajv.compile(schema2)}) as MotionScript;
    if(script.chapter!==`${series}/${chapter}`)throw Error('Offline chapter identity mismatch');
    const manifestResponse=await fetch(base+'/manifest');if(!manifestResponse.ok)throw Error('Offline integrity manifest unavailable');
    const manifest=await manifestResponse.json(),assets=chapterAssets(script);
    if(manifest.snapshot!==info.snapshot||JSON.stringify(Object.keys(manifest.assets??{}).sort())!==JSON.stringify(assets)||Object.values(manifest.assets).some(h=>typeof h!=='string'||!/^[a-f0-9]{64}$/.test(h)))throw Error('Offline integrity manifest mismatch');
    const previous=(await offlineChapters()).find(r=>r.series===series&&r.chapter===chapter);
    const cacheName=PREFIX+crypto.randomUUID(),cache=await caches.open(cacheName);let bytes=scriptBytes.length;
    try{
      for(const orphan of await caches.keys())if(orphan.startsWith(PREFIX)&&!(await offlineChapters()).some(r=>r.cacheName===orphan)&&orphan!==cacheName)await caches.delete(orphan);
      const occupied=(await offlineChapters()).reduce((n,r)=>n+r.bytes,0),estimate=await navigator.storage.estimate();
      const available=Math.min(BUDGET-occupied,(estimate.quota??BUDGET)-(estimate.usage??0)-16*2**20);
      if(bytes>available)throw Error('Offline storage is full; remove a saved chapter');
      await cache.put(info.script_url,new Response(scriptBytes,{headers:{'Content-Type':'application/json'}}));
      onProgress(0,assets.length);
      for(let i=0;i<assets.length;i++){
        const url=info.asset_base+assets[i],asset=await fetch(url,{cache:'no-store'}),mime=asset.headers.get('content-type')??'application/octet-stream';
        const data=await limitedBytes(asset);if(await bytesHash(data)!==manifest.assets[assets[i]])throw Error('Offline asset hash mismatch: '+assets[i]);
        bytes+=data.length;if(bytes>available)throw Error('Offline storage is full; remove a saved chapter');
        await cache.put(url,new Response(data,{headers:{'Content-Type':mime}}));onProgress(i+1,assets.length);
      }
      const record:Saved={series,chapter,cacheName,bytes,playbackUrl,info:{...info,partial:false},savedAt:new Date().toISOString()};
      // Commit one pointer only after every declared asset is verified and stored.
      await (await caches.open(INDEX)).put(key(series,chapter),Response.json(record));
      if(previous)await caches.delete(previous.cacheName);return record;
    }catch(e){await caches.delete(cacheName);throw e;}
  });
}
export async function removeChapter(series:string,chapter:string){
  if(!navigator.locks)throw Error('Offline removal needs browser storage locks');
  await navigator.locks.request('mm-offline-write',async()=>{const index=await caches.open(INDEX),response=await index.match(key(series,chapter));if(response){const record:Saved=await response.json();await index.delete(key(series,chapter));await caches.delete(record.cacheName);}});
}
