import test from 'node:test';
import assert from 'node:assert/strict';
import {duckPoints,gainAt,scheduleDuck} from '../src/sfx.js';
test('voice overlap merges duck windows and decoded voice extends the hold',()=>{
 const panel={timeline:[{type:'line',t:1,dur:1,audio:'a'},{type:'line',t:1.5,dur:2,audio:'b'}]};
 const points=duckPoints(panel,{b:3},.2);
 assert.equal(gainAt(points,1.5),.5);assert.equal(gainAt(points,4.6),.5);assert.equal(gainAt(points,5),1);
 assert.equal(gainAt(duckPoints({timeline:[]}),100),1);
});
test('resume schedules remaining duck envelope independently of user mute bus',()=>{
 const calls=[],param={cancelScheduledValues:t=>calls.push(['cancel',t]),setValueAtTime:(v,t)=>calls.push(['set',v,t]),linearRampToValueAtTime:(v,t)=>calls.push(['ramp',v,t])};
 const points=duckPoints({timeline:[{type:'line',t:1,dur:1,audio:'a'}]});
 scheduleDuck(param,points,1.5,10);
 assert.deepEqual(calls[1],['set',.5,10]);assert.ok(calls.slice(2).every(c=>c[2]>10));assert.equal(calls.at(-1)[1],1);
});
