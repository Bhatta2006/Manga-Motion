import {test} from 'node:test';
import assert from 'node:assert/strict';
import {activeBubble,hitText,tapDirection} from '../src/bubble-state.js';
test('glow uses decoded output duration and referenced bubble; missing audio has no glow',()=>{
  const line={type:'line',audio:'a.wav',t:1,dur:.2,bubble:'b',highlight:true};
  const panel={timeline:[line],director:{focus:[{kind:'bubble',ref:'b',bbox:[0,0,10,10]}]}};
  const clips=new Map([['a.wav',{duration:2}]]);
  assert.equal(activeBubble(panel,.99,clips).line,null);assert.deepEqual(activeBubble(panel,2.9,clips).bbox,[0,0,10,10]);assert.equal(activeBubble(panel,3,clips).line,null);
  assert.equal(activeBubble(panel,2,new Map()).bbox,null);
  line.highlight=false;assert.equal(activeBubble(panel,2,clips).bbox,null);
});
test('overlapping text hits pick smallest region; RTL/LTR tap zones mirror',()=>{
  const a={id:'a',bbox:[0,0,20,20]},b={id:'b',bbox:[5,5,10,10]};assert.equal(hitText([a,b],7,7),b);assert.equal(hitText([a,b],21,7),null);
  for(const direction of ['rtl','ltr']){assert.equal(tapDirection(5,100,direction),direction==='rtl'?1:-1);assert.equal(tapDirection(95,100,direction),direction==='rtl'?-1:1);assert.equal(tapDirection(50,100,direction),0);}
});
