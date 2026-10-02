import {validateMotionScript} from './contract.js';
import {ease} from './core.js';
const contains=(a,b)=>a[0]<=b[0]+1e-7&&a[1]<=b[1]+1e-7&&a[2]+1e-7>=b[2]&&a[3]+1e-7>=b[3];
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
export async function contentHash(value){const bytes=new TextEncoder().encode(JSON.stringify(canonical(value)));return bytesHash(bytes);}
export async function bytesHash(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');}
export async function validateSupportedScript(script,validators){
  if(script.version===1)return validateMotionScript(script,validators[1]);
  if(script.version!==2)throw Error('Unsupported MotionScript version: '+script.version);
  if(!validators[2](script))throw Error('Invalid MotionScript v2: '+JSON.stringify(validators[2].errors));
  const common=structuredClone(script);common.version=1;delete common.scenes;
  for(const page of common.pages)for(const panel of page.panels){delete panel.scene;delete panel.layers;for(const e of panel.timeline)if(e.type==='camera')e.ease='linear';}
  validateMotionScript(common,validators[1]);
  for(const scene of Object.values(script.scenes)){
    const buses=new Set(),ids=new Set();
    for(const b of scene.beds){
      if(buses.has(b.bus)||ids.has(b.id)||!b.file.startsWith(b.bus+'/'))throw Error('Duplicate bed ID/bus or incorrect asset role');
      buses.add(b.bus);ids.add(b.id);
      if(!(b.loop[0]<b.loop[1]&&b.loop[1]<=b.duration&&b.fade_seconds<=b.loop[1]-b.loop[0]))throw Error('Invalid bed loop/fade extent');
    }
  }
  for(const page of script.pages)for(const panel of page.panels){
    if(panel.scene!==undefined&&!Object.hasOwn(script.scenes,panel.scene))throw Error('Unknown scene');
    const ids=new Set();
    for(const layer of panel.layers??[]){
      if(ids.has(layer.id)||layer.source_page!==page.id)throw Error('Invalid layer source/ID');ids.add(layer.id);
      const r=layer.source_bbox;
      if(!(r[0]<r[2]&&r[1]<r[3]&&contains(panel.bbox,r)))throw Error('Invalid layer bounds');
      const first=layer.poses[0];
      if(first.u!==0||first.scale!==1||first.offset.some(x=>x!==0)||layer.poses.at(-1).u!==1||layer.poses.some((p,i)=>i>0&&p.u<=layer.poses[i-1].u))throw Error('Invalid layer pose sequence');
      if(layer.safety.transform_sha256!==await contentHash({source_bbox:r,anchor:layer.anchor,poses:layer.poses}))throw Error('Stale layer transform safety binding');
    }
    for(const event of panel.timeline.filter(e=>e.type==='camera')){
      const times=event.ease==='outBack'?[0,1,1-2*1.70158/(3*2.70158)]:[0,1];
      for(const u of times){
        const p=ease(u,event.ease),r=event.from.map((v,i)=>v+(event.to[i]-v)*p);
        if(!(r[0]<r[2]&&r[1]<r[3]&&contains([0,0,...page.size],r)&&(event.from[2]-event.from[0])/(r[2]-r[0])<=1.4+1e-7))throw Error('Unsafe eased camera extent');
        if(panel.director.focus.some(f=>f.kind==='bubble'&&!contains(r,f.bbox)))throw Error('Easing crops protected text');
      }
    }
  }
  return script;
}
