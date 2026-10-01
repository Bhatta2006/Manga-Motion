import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import Ajv from 'ajv';
import {cameraAt,durationOf,outputTime,poseOf} from '../src/core.js';

const schema=JSON.parse(fs.readFileSync(new URL('../../schema/motionscript-v1.schema.json',import.meta.url)));
const validate=new Ajv({allErrors:true}).compile(schema);
const file=new URL('../../library/preview/m0b/motionscript.json',import.meta.url);
const script=JSON.parse(fs.readFileSync(file));

test('all five real pages conform to v1 schema',()=>{assert.ok(validate(script),JSON.stringify(validate.errors));assert.equal(script.pages.length,5);assert.equal(script.pages.reduce((s,p)=>s+p.panels.length,0),25);});
test('golden cameras preserve all protected text through 101 samples',()=>{
  for(const page of script.pages)for(const panel of page.panels){
    const duration=durationOf(panel);
    const camera=panel.timeline.find(e=>e.type==='camera');
    const a=camera.from,b=camera.to;
    const zoom=Math.max((a[2]-a[0])/(b[2]-b[0]),(b[2]-b[0])/(a[2]-a[0]));
    assert.ok(zoom<=1.4);assert.ok((zoom-1)/camera.dur*Math.PI/2<=.6);
    for(let j=0;j<=100;j++){
      const rect=cameraAt(panel,duration*j/100);
      assert.ok(rect[0]>=0&&rect[1]>=0&&rect[2]<=page.size[0]&&rect[3]<=page.size[1]);
      for(const f of panel.director.focus.filter(f=>f.kind==='bubble'))assert.ok(rect[0]<=f.bbox[0]&&rect[1]<=f.bbox[1]&&rect[2]>=f.bbox[2]&&rect[3]>=f.bbox[3]);
    }
  }
});
test('future dialogue remains a v1 event and extends the audio timeline',()=>{
  const clone=structuredClone(script);
  const panel=clone.pages[0].panels[0];
  panel.timeline.push({type:'line',t:2,bubble:'b0',speaker:'narrator',text:'A future voice line.',audio:'audio/test.wav',dur:20,emotion:{delivery:'narrate',intensity:.2},highlight:true});
  assert.ok(validate(clone),JSON.stringify(validate.errors));assert.equal(durationOf(panel),22.4);
  panel.timeline.at(-1).audio='../.env';assert.equal(validate(clone),false);
});
test('audible clock compensates output latency and rejects stale stamps',()=>{
  assert.equal(outputTime({currentTime:5,getOutputTimestamp:()=>({contextTime:4.9,performanceTime:1000})},1020),4.92);
  assert.ok(Math.abs(outputTime({currentTime:5,baseLatency:.01,outputLatency:.02,getOutputTimestamp:()=>({contextTime:1,performanceTime:0})},1020)-4.97)<1e-8);
});
test('decoded voice extends dwell while music never sets the reading timer',()=>{
  const panel={timeline:[{type:'camera',t:0,dur:2},{type:'line',t:1,dur:3,audio:'audio/a.wav'}]};
  assert.equal(durationOf(panel,{'audio/a.wav':10}),11.4);
  panel.timeline.push({type:'music',t:0,dur:600});assert.equal(durationOf(panel,{'audio/a.wav':10}),11.4);
});
test('parallax poses always cover original source rectangle',()=>{
  const box=[10,10,210,110];
  for(let i=0;i<=100;i++){
    const p=poseOf(box,i/100);assert.ok(10-200*(p.scale-1)/2+p.dx<=10);assert.ok(210+200*(p.scale-1)/2+p.dx>=210);
    assert.ok(10-100*(p.scale-1)/2+p.dy<=10);assert.ok(110+100*(p.scale-1)/2+p.dy>=110);
  }
});
