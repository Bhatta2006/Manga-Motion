import {cameraAt,interpolate,clamp} from './core.js';
export const MOTION_LEVELS={subtle:.35,normal:.7,hype:1};
export function styledCamera(panel,time,preset='normal',reduce=false){
  const start=panel.timeline.find(e=>e.type==='camera')?.from??panel.bbox;
  return reduce?start:interpolate(start,cameraAt(panel,time),MOTION_LEVELS[preset]??.7);
}
export function shakeEligible(page,panel){
  const impact=page.panels.filter(p=>p.director.beat==='impact'&&p.director.energy>=.5&&p.timeline.some(e=>e.type==='camera'&&e.move!=='hold'));
  return impact.slice(0,3).some(p=>p.id===panel.id);
}
export function protectedShake(panel,rect){
  const w=rect[2]-rect[0],h=rect[3]-rect[1];
  return panel.director.focus.filter(f=>f.kind==='bubble').every(f=>f.bbox[0]>=rect[0]+w*.02&&f.bbox[2]<=rect[2]-w*.02&&f.bbox[1]>=rect[1]+h*.02&&f.bbox[3]<=rect[3]-h*.02);
}
export function sceneEffects(panel,time,preset='normal',reduce=false,canShake=false){
  if(reduce||time<0)return {dx:0,dy:0,flash:0,vignette:0};
  const strength=MOTION_LEVELS[preset]??.7,energy=panel.director.energy;
  const decay=canShake&&time<.25?(1-clamp(time/.25))**2:0;
  const shock=panel.director.beat==='reaction'&&panel.director.shot==='extreme_closeup'&&energy>=.8&&panel.timeline.some(e=>e.type==='camera'&&e.move!=='hold');
  return {dx:decay?Math.sin(time*91)*.012*energy*strength*decay:0,
          dy:decay?Math.sin(time*117)*.008*energy*strength*decay:0,
          flash:shock&&time>=.18&&time<.18+1/60?.1*strength:0,
          vignette:panel.director.beat==='flashback'?.1*strength:0};
}
