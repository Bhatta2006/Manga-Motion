import test from 'node:test';
import assert from 'node:assert/strict';
import {styledCamera,sceneEffects,shakeEligible,protectedShake} from '../src/motion-settings.js';
const panel={id:'p0',bbox:[0,0,1000,800],director:{beat:'impact',shot:'closeup',energy:1,focus:[]},timeline:[{type:'camera',t:0,dur:2,move:'push_in',from:[0,0,1000,800],to:[100,80,900,720],ease:'inOutSine'}]};
test('all motion strengths interpolate inside solved camera bounds and reduce holds',()=>{
  for(const name of ['subtle','normal','hype'])for(let i=0;i<=100;i++){
    const pose=styledCamera(panel,i/50,name);
    assert.ok(pose[0]>=0&&pose[0]<=100&&pose[2]>=900&&pose[2]<=1000);
    assert.deepEqual(styledCamera(panel,i/50,name,true),panel.timeline[0].from);
  }
  assert.ok(styledCamera(panel,2,'hype')[0]>styledCamera(panel,2,'normal')[0]);
});
test('impact shakes are capped at three/page, decay and protect bubbles',()=>{
  const page={panels:Array.from({length:5},(_,i)=>({...panel,id:'p'+i}))};
  assert.equal(page.panels.filter(p=>shakeEligible(page,p)).length,3);
  for(let i=0;i<=300;i++){const fx=sceneEffects(panel,i/1000,'hype',false,true);assert.ok(Math.abs(fx.dx)<=.015&&Math.abs(fx.dy)<=.015);if(i>=250)assert.equal(fx.dx,0);}
  assert.equal(protectedShake({...panel,director:{...panel.director,focus:[{kind:'bubble',bbox:[0,0,100,100]}]}},[0,0,1000,800]),false);
  assert.deepEqual(sceneEffects(panel,.08,'hype',true,true),{dx:0,dy:0,flash:0,vignette:0});
});
test('shock flash and flashback treatment remain clock-bounded and reduced-motion safe',()=>{
  const shock={...panel,director:{...panel.director,beat:'reaction',shot:'extreme_closeup'}};
  assert.ok(sceneEffects(shock,.185).flash>0);assert.equal(sceneEffects(shock,.21).flash,0);
  assert.equal(sceneEffects(shock,.185,'normal',true).flash,0);
  const past={...panel,director:{...panel.director,beat:'flashback'}};
  assert.ok(sceneEffects(past,2).vignette>0);
});
