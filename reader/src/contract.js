// Geometry/reference checks supplement the unchanged v1 JSON Schema.
const number=(v)=>typeof v==='number'&&Number.isFinite(v);
const contains=(a,b)=>a[0]<=b[0]+1e-7&&a[1]<=b[1]+1e-7&&a[2]+1e-7>=b[2]&&a[3]+1e-7>=b[3];
function checkRect(r,size,label) {
  if(!Array.isArray(r)||r.length!==4||!r.every(number)||!(0<=r[0]&&r[0]<r[2]&&r[2]<=size[0]&&0<=r[1]&&r[1]<r[3]&&r[3]<=size[1]))throw Error(`${label}: invalid page rectangle`);
}
function checkPath(path,kind) {
  if(typeof path!=='string'||!new RegExp(`^${kind}/[A-Za-z0-9_.-]+$`).test(path)||['.','..'].includes(path.split('/')[1]))throw Error(`Invalid ${kind} asset path`);
}

export function validateMotionScript(script,validateSchema) {
  if(!validateSchema(script))throw Error('Invalid MotionScript v1: '+JSON.stringify(validateSchema.errors));
  const ids=new Set();
  for(const page of script.pages) {
    checkPath(page.image,'pages');
    for(const item of [page,...page.panels]) {
      if(!item.id||ids.has(item.id))throw Error('Missing or duplicate page/panel ID');
      ids.add(item.id);
    }
    for(const panel of page.panels) {
      checkRect(panel.bbox,page.size,'Panel');
      const bubbles=new Map();
      for(const focus of panel.director.focus) {
        checkRect(focus.bbox,page.size,'Focus');
        if(focus.char!==undefined&&!Object.hasOwn(script.characters,focus.char))throw Error('Unknown focus character');
        if(focus.kind==='bubble'&&focus.ref) {
          if(bubbles.has(focus.ref))throw Error('Duplicate bubble reference');
          bubbles.set(focus.ref,focus.bbox);
        }
      }
      let lastTime=-1, cameraEnd=-1, previousCamera=null, cameras=0;
      for(const event of panel.timeline) {
        if(!number(event.t)||event.t<lastTime)throw Error('Invalid or unsorted timeline time');
        lastTime=event.t;
        if(event.type==='camera') {
          cameras++;
          if(!number(event.dur)||event.dur<=0||!number(event.t+event.dur))throw Error('Invalid camera duration');
          if((cameras===1&&event.t!==0)||event.t<cameraEnd-1e-7)throw Error('Missing initial or overlapping camera event');
          checkRect(event.from,page.size,'Camera start');checkRect(event.to,page.size,'Camera end');
          if(previousCamera&&!event.from.every((v,i)=>Math.abs(v-previousCamera[i])<=1e-7))throw Error('Discontinuous camera events');
          for(const focus of panel.director.focus.filter(f=>f.kind==='bubble')) {
            if(!contains(event.from,focus.bbox)||!contains(event.to,focus.bbox))throw Error('Camera crops protected text');
          }
          cameraEnd=event.t+event.dur;previousCamera=event.to;
        } else if(event.type==='line') {
          checkPath(event.audio,'audio');
          if(!number(event.dur)||event.dur<=0||!number(event.t+event.dur))throw Error('Invalid line duration');
          if(!Object.hasOwn(script.characters,event.speaker))throw Error('Unknown speaker');
          // v1 does not require a bubble box registry; a line may have only face focus.
          if(!event.bubble)throw Error('Missing line bubble reference');
        } else if(event.type==='sfx')checkPath(event.file,'sfx');
      }
      if(!cameras)throw Error('Panel requires an initial camera event');
    }
  }
  return script;
}
