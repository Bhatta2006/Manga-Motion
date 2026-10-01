import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import Ajv from 'ajv';
import {validateMotionScript} from '../src/contract.js';
import {cameraAt,durationOf} from '../src/core.js';
const schema=JSON.parse(fs.readFileSync(new URL('../../schema/motionscript-v1.schema.json',import.meta.url)));
const check=new Ajv({allErrors:true}).compile(schema);
const original=JSON.parse(fs.readFileSync(new URL('../../schema/examples/basic.json',import.meta.url)));
const valid=s=>validateMotionScript(s,check);

test('public fixture and existing real preview retain v1 compatibility',()=>{
  valid(original);
  valid(JSON.parse(fs.readFileSync(new URL('../../library/preview/m0b/motionscript.json',import.meta.url))));
});
test('invalid geometry/time/references fail before Pixi initialization',()=>{
  const changes=[p=>p.bbox[2]=NaN,p=>p.timeline[0].dur=Infinity,p=>p.timeline[0].t=1,
    p=>p.timeline.push({...p.timeline[0],t:1}),p=>p.timeline[0].from=[700,130,870,290],
    p=>p.timeline[0].ease='invented',p=>p.director.focus[0].char='unknown'];
  for(const change of changes){const s=structuredClone(original);change(s.pages[0].panels[0]);assert.throws(()=>valid(s));}
  const s=structuredClone(original);s.pages[0].image='audio/wrong.wav';assert.throws(()=>valid(s));
  const d=structuredClone(original);d.pages.push(structuredClone(d.pages[0]));assert.throws(()=>valid(d));
});
test('v1 future lines may reference bubbles without requiring a new registry field',()=>{
  const s=structuredClone(original);s.characters.narrator={voice:'future'};
  s.pages[0].panels[0].timeline.push({t:2,type:'line',bubble:'unboxed',speaker:'narrator',text:'future',audio:'audio/line.wav',dur:20,emotion:{delivery:'narrate',intensity:.2},highlight:false});
  valid(s);assert.equal(durationOf(s.pages[0].panels[0]),22.4);
  s.pages[0].panels[0].timeline.at(-1).speaker='missing';assert.throws(()=>valid(s));
});
test('reader validates all compiled real panels and preserves text at 101 timestamps',()=>{
  const script=JSON.parse(fs.readFileSync(new URL('../../library/golden-m1b/chapter/motionscript.json',import.meta.url)));valid(script);
  assert.equal(script.pages.length,5);
  for(const page of script.pages)for(const panel of page.panels)for(let i=0;i<=100;i++){
    const r=cameraAt(panel,durationOf(panel)*i/100);
    assert.ok(r[0]>=0&&r[1]>=0&&r[2]<=page.size[0]&&r[3]<=page.size[1]);
    for(const b of panel.director.focus.filter(f=>f.kind==='bubble').map(f=>f.bbox))assert.ok(r[0]<=b[0]+1e-7&&r[1]<=b[1]+1e-7&&r[2]+1e-7>=b[2]&&r[3]+1e-7>=b[3]);
  }
});
