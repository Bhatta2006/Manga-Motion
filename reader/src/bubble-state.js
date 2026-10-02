/** Clock selection uses decoded duration, matching the actual Web Audio source. */
export function activeBubble(panel,time,clips){
  const line=panel.timeline.find(e=>e.type==='line'&&clips.has(e.audio)&&time>=e.t&&time<e.t+clips.get(e.audio).duration);
  const focus=line?.highlight?panel.director.focus.find(f=>f.kind==='bubble'&&f.ref===line.bubble):null;
  return {line:line??null,bbox:focus?.bbox??null};
}
export function hitText(texts,x,y){
  // Smallest enclosing text wins overlapping boxes; stable ID breaks equal areas.
  return texts.filter(t=>x>=t.bbox[0]&&x<=t.bbox[2]&&y>=t.bbox[1]&&y<=t.bbox[3]).sort((a,b)=>(a.bbox[2]-a.bbox[0])*(a.bbox[3]-a.bbox[1])-(b.bbox[2]-b.bbox[0])*(b.bbox[3]-b.bbox[1])||a.id.localeCompare(b.id))[0]??null;
}
export function tapDirection(x,width,direction){return x<width*.28?(direction==='rtl'?1:-1):x>width*.72?(direction==='rtl'?-1:1):0;}
