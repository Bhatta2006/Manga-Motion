import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import Ajv from 'ajv';
import {validateSupportedScript} from '../src/contract-v2.js';import {ease,durationOf} from '../src/core.js';
const load=async name=>JSON.parse(await fs.readFile(new URL('../../schema/'+name,import.meta.url),'utf8'));
const ajv=new Ajv({allErrors:true}),validators={1:ajv.compile(await load('motionscript-v1.schema.json')),2:ajv.compile(await load('motionscript-v2.schema.json'))};
test('shared production guard accepts both versions and approved examples',async()=>{
 for(const file of ['examples/basic.json','proposals/v2-flat.example.json','proposals/v2-music-depth.example.json','proposals/v2-spring.example.json'])assert.ok(await validateSupportedScript(await load(file),validators));
 const script=await load('proposals/v2-music-depth.example.json');
 const before=durationOf(script.pages[0].panels[0]);script.scenes.calm_1.beds[0].duration=86400;script.scenes.calm_1.beds[0].loop=[0,86400];
 await validateSupportedScript(script,validators);assert.equal(durationOf(script.pages[0].panels[0]),before);
});
test('shared production guard rejects stale layers, bad bed roles, unknown versions and unsafe spring overshoot',async()=>{
 const source=await load('proposals/v2-music-depth.example.json');
 for(const mutate of [s=>s.version=3,s=>s.pages[0].panels[0].layers[0].poses[1].offset=[.01,0],s=>s.scenes.calm_1.beds[0].file='ambience/wrong.wav',s=>s.pages[0].panels[0].scene='unknown',s=>{const p=s.pages[0].panels[0];p.timeline[0].ease='outBack';p.director.focus.push({kind:'bubble',bbox:[100,300,110,400]});}]){
  const s=structuredClone(source);mutate(s);await assert.rejects(()=>validateSupportedScript(s,validators));
 }
 assert.equal(ease(0,'outExpo'),0);assert.equal(ease(1,'outExpo'),1);assert.ok(ease(.6,'outBack')>1);
});
