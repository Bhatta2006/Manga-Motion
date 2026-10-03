import {test} from 'node:test';
import assert from 'node:assert/strict';
import {layerPose} from '../src/layer-pose.js';
import {contentHash} from '../src/contract-v2.js';
test('layer interpolation stays in approved linear envelope including clamped playback ends',()=>{
  const layer={poses:[{u:0,scale:1,offset:[0,0]},{u:.4,scale:1.06,offset:[.01,0]},{u:1,scale:1.01,offset:[0,.01]}]};
  for(let i=-1;i<=101;i++){const p=layerPose(layer,i/100);assert.ok(p.scale>=1&&p.scale<=1.06);assert.ok(p.offset.every(v=>v>=0&&v<=.01));}
  assert.equal(layerPose(layer,.4).scale,1.06);assert.deepEqual(layerPose(layer,-1),{scale:1,offset:[0,0]});
});
test('transform identity is identical for integral numbers regardless of producer float spelling',async()=>{
  const a={source_bbox:[0,0,10,10],anchor:[.5,1],poses:[{u:0,scale:1,offset:[0,0]},{u:1,scale:1.01,offset:[0,0]}]};
  const b=JSON.parse(JSON.stringify(a).replace('"anchor":[0.5,1]','"anchor":[0.5,1.0]'));assert.equal(await contentHash(a),await contentHash(b));
});
