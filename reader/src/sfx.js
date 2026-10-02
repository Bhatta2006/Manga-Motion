// Pure voice windows/envelopes; the user mute bus remains independent.
export function duckPoints(panel,durations={},transition=0){
  const windows=panel.timeline.filter(e=>e.type==='line').map(e=>[e.t+transition,e.t+transition+Math.max(e.dur,durations[e.audio]??0)]).sort((a,b)=>a[0]-b[0]);
  const merged=[];
  for(const window of windows){const last=merged.at(-1);if(last&&window[0]<=last[1]+.14)last[1]=Math.max(last[1],window[1]);else merged.push([...window]);}
  const points=[[0,1]];
  for(const [start,end] of merged)points.push([Math.max(0,start-.02),1],[start,.5],[end,.5],[end+.12,1]);
  return points;
}
export function gainAt(points,time){
  let previous=points[0];
  for(const point of points.slice(1)){
    if(point[0]>time){const span=point[0]-previous[0];return span?previous[1]+(point[1]-previous[1])*Math.max(0,(time-previous[0])/span):point[1];}
    previous=point;
  }
  return previous[1];
}
export function scheduleDuck(param,points,offset,now){
  param.cancelScheduledValues(now);param.setValueAtTime(gainAt(points,offset),now);
  for(const [t,value] of points)if(t>offset)param.linearRampToValueAtTime(value,now+t-offset);
}
