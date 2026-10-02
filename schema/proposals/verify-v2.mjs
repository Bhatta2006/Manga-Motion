// Proposal-only verifier. Production continues to reject v2 until user approval.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import Ajv from '../../reader/node_modules/ajv/dist/ajv.js';
import {validateMotionScript} from '../../reader/src/contract.js';

const root=path.resolve(import.meta.dirname,'../..'),dir=import.meta.dirname,start=performance.now();
const read=async name=>JSON.parse(await fs.readFile(path.join(dir,name),'utf8'));
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const canonical=value=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])):value;
const hash=value=>sha(JSON.stringify(canonical(value)));
const clone=value=>structuredClone(value);
const ajv=new Ajv({allErrors:true,strict:true});
const proposed=await read('motionscript-v2.schema.json'),validate=ajv.compile(proposed);
const v1Schema=JSON.parse(await fs.readFile(path.join(root,'schema/motionscript-v1.schema.json'),'utf8'));
const validateV1=ajv.compile(v1Schema);
const base=JSON.parse(await fs.readFile(path.join(root,'schema/examples/basic.json'),'utf8'));
const contains=(a,b)=>a[0]<=b[0]+1e-7&&a[1]<=b[1]+1e-7&&a[2]+1e-7>=b[2]&&a[3]+1e-7>=b[3];
const ease=(name,u)=>name==='outBack'?1+2.70158*(u-1)**3+1.70158*(u-1)**2:name==='outExpo'?(1-2**(-10*u))/(1-2**-10):name==='outQuad'?1-(1-u)**2:name==='inOutSine'?(1-Math.cos(Math.PI*u))/2:u;
function check(script){
  assert.ok(validate(script),JSON.stringify(validate.errors));
  // Test only: project common geometry onto v1 to reuse its established guards.
  // This is not a supported/lossless downgrade of an enriched chapter.
  const common=clone(script);common.version=1;delete common.scenes;
  for(const page of common.pages)for(const panel of page.panels){delete panel.scene;delete panel.layers;for(const e of panel.timeline)if(e.type==='camera')e.ease='linear';}
  validateMotionScript(common,validateV1);
  for(const scene of Object.values(script.scenes)){
    const buses=new Set(),ids=new Set();
    for(const bed of scene.beds){
      assert.ok(!buses.has(bed.bus),'Duplicate scene bus');buses.add(bed.bus);
      assert.ok(!ids.has(bed.id),'Duplicate bed ID');ids.add(bed.id);
      assert.ok(bed.file.startsWith(bed.bus+'/'),'Bed role/path mismatch');
      assert.ok(bed.loop[0]<bed.loop[1]&&bed.loop[1]<=bed.duration,'Invalid loop extent');
      assert.ok(bed.fade_seconds<=bed.loop[1]-bed.loop[0],'Fade longer than loop');
    }
  }
  for(const page of script.pages)for(const panel of page.panels){
    assert.ok(panel.scene===undefined||Object.hasOwn(script.scenes,panel.scene),'Unknown scene');
    const ids=new Set();
    for(const layer of panel.layers??[]){
      assert.ok(!ids.has(layer.id),'Duplicate layer ID');ids.add(layer.id);
      assert.equal(layer.source_page,page.id,'Layer must sample its current original page');
      const r=layer.source_bbox;
      assert.ok(r[0]<r[2]&&r[1]<r[3]&&contains(panel.bbox,r),'Invalid source bounds');
      assert.deepEqual(layer.poses[0],{u:0,scale:1,offset:[0,0]},'Layer must start flat');
      assert.equal(layer.poses.at(-1).u,1,'Layer must finish at u=1');
      assert.ok(layer.poses.every((p,i)=>i===0||p.u>layer.poses[i-1].u),'Unsorted layer poses');
      assert.equal(layer.safety.transform_sha256,hash({source_bbox:layer.source_bbox,anchor:layer.anchor,poses:layer.poses}),'Stale transform safety binding');
    }
    for(const event of panel.timeline.filter(e=>e.type==='camera')){
      const times=Array.from({length:1001},(_,i)=>i/1000);
      if(event.ease==='outBack')times.push(1-2*1.70158/(3*2.70158));
      for(const u of times){
        const p=ease(event.ease,u),rect=event.from.map((v,i)=>v+(event.to[i]-v)*p);
        assert.ok(rect.every(Number.isFinite)&&rect[0]<rect[2]&&rect[1]<rect[3]&&contains([0,0,...page.size],rect),'Easing leaves source bounds');
        assert.ok((event.from[2]-event.from[0])/(rect[2]-rect[0])<=1.4+1e-7,'Easing exceeds zoom cap');
        for(const focus of panel.director.focus.filter(f=>f.kind==='bubble'))assert.ok(contains(rect,focus.bbox),'Easing crops protected text');
      }
    }
  }
  return script;
}
const fixtures=['v2-flat.example.json','v2-music-depth.example.json','v2-spring.example.json'];
const values=await Promise.all(fixtures.map(read));values.forEach(check);
let negativeCases=0;
function rejects(name,mutate){const v=clone(values[1]);mutate(v);assert.throws(()=>check(v),undefined,name);negativeCases++;}
const panel=s=>s.pages[0].panels[0],bed=s=>s.scenes.calm_1.beds[0],layer=s=>panel(s).layers[0];
rejects('unknown scene',s=>panel(s).scene='missing');
rejects('path traversal',s=>bed(s).file='music/../secret.wav');
rejects('bus mismatch',s=>bed(s).file='ambience/quiet.wav');
rejects('duplicate bus',s=>s.scenes.calm_1.beds[1].bus='music');
rejects('reversed loop',s=>bed(s).loop=[10,2]);
rejects('loop outside clip',s=>bed(s).loop=[0,13]);
rejects('unbounded level',s=>bed(s).gain_db=0);
rejects('other source page',s=>layer(s).source_page='p002');
rejects('generated source image',s=>layer(s).image='layers/regenerated.png');
rejects('mask wrong role',s=>layer(s).mask='pages/001.png');
rejects('mask URL',s=>layer(s).mask='https://example.invalid/mask.png');
rejects('degenerate bounds',s=>layer(s).source_bbox=[200,200,200,550]);
rejects('excessive translation',s=>layer(s).poses[1].offset=[.03,0]);
rejects('excessive scale',s=>layer(s).poses[1].scale=1.1);
rejects('nonzero uncovered pixels',s=>layer(s).safety.max_uncovered_pixels=1);
rejects('stale transform binding',s=>layer(s).poses[1].offset=[.009,0]);
rejects('pose order',s=>layer(s).poses[1].u=0);
rejects('nonflat start',s=>layer(s).poses[0].scale=1.01);
rejects('unknown root field',s=>s.generated_background=true);
rejects('outBack crop during overshoot',s=>{const p=panel(s);p.timeline[0].ease='outBack';p.director.focus.push({kind:'bubble',ref:'edge-test',bbox:[100,300,110,400]});});

validateMotionScript(base,validateV1);
const promoted=clone(base);promoted.version=2;promoted.scenes={};check(promoted);
const restored=clone(promoted);restored.version=1;delete restored.scenes;assert.deepEqual(restored,base);
const unchanged=await read('v1-baseline.json');
for(const [file,digest] of Object.entries(unchanged.files))assert.equal(sha((await fs.readFile(path.join(root,file),'utf8')).replaceAll('\r\n','\n')),digest,'Production v1 changed: '+file);
assert.ok(!validateV1(values[1]),'Production schema must reject unapproved v2');
// Music is not a timeline event; even a day-long bed cannot extend panel dwell.
const cameraEnd=s=>s.pages.flatMap(p=>p.panels).map(p=>Math.max(...p.timeline.filter(e=>e.type==='camera').map(e=>e.t+e.dur)));
const long=clone(values[1]);bed(long).duration=86400;bed(long).loop=[0,86400];check(long);
assert.deepEqual(cameraEnd(long),cameraEnd(values[1]));
for(const name of ['outExpo','outBack']){assert.ok(Math.abs(ease(name,0))<1e-12);assert.equal(ease(name,1),1);}
let realV1PagesValidated=0;
for(const file of process.argv.slice(2)){
  const original=JSON.parse(await fs.readFile(path.resolve(root,file),'utf8'));validateMotionScript(original,validateV1);
  const upgraded=clone(original);upgraded.version=2;upgraded.scenes={};check(upgraded);
  const downgraded=clone(upgraded);downgraded.version=1;delete downgraded.scenes;assert.deepEqual(downgraded,original);
  assert.deepEqual(cameraEnd(upgraded),cameraEnd(original));realV1PagesValidated+=original.pages.length;
}
const sizes=Object.fromEntries(await Promise.all(['motionscript-v2.schema.json',...fixtures].map(async name=>[name,(await fs.stat(path.join(dir,name))).size])));
console.log(JSON.stringify({status:'proposal verification passed',fixtures:fixtures.length,negativeCases,realV1PagesValidated,v1RoundTrip:true,productionV1Unchanged:true,productionRejectsV2:true,longMusicDoesNotExtendCamera:true,easingChecks:'1001 points plus exact outBack extremum; structural/geometry only',sizes,elapsedMs:performance.now()-start,peakProcessRssMiB:process.resourceUsage().maxRSS/1024,heavyModelsLoaded:0},null,2));
