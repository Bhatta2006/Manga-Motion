// Pure timeline math shared by playback and Node tests.
export function clamp(value, low = 0, high = 1) { return Math.min(high, Math.max(low, value)); }
export function ease(t, name) {
  t=clamp(t);
  return name==='inOutSine' ? (1-Math.cos(Math.PI*t))/2 : name==='outQuad' ? 1-(1-t)**2 : t;
}
export function interpolate(a,b,t) { return a.map((v,i)=>v+(b[i]-v)*t); }
export function cameraAt(panel,time) {
  const events=panel.timeline.filter(e=>e.type==='camera');
  let rect=events[0]?.from ?? panel.bbox;
  for (const event of events) {
    if (time<event.t) break;
    rect=interpolate(event.from,event.to,ease((time-event.t)/event.dur,event.ease));
  }
  return rect;
}
export function durationOf(panel, clipDurations = {}) {
  return Math.max(...panel.timeline.map(e=>e.t+(e.type==='camera'||e.type==='line'?e.dur:(clipDurations[e.file]??0))),.8)+.4;
}
export function poseOf(box,phase) {
  return {scale:1.02,dx:Math.sin(phase*Math.PI*2)*(box[2]-box[0])*.004,dy:Math.sin(phase*Math.PI)*(box[3]-box[1])*.004};
}
export function outputTime(context,now) {
  const stamp=context.getOutputTimestamp?.();
  if (stamp?.performanceTime>0 && now-stamp.performanceTime>=0 && now-stamp.performanceTime<1000) {
    return Math.min(context.currentTime,stamp.contextTime+(now-stamp.performanceTime)/1000);
  }
  return Math.max(0,context.currentTime-(context.baseLatency??0)-(context.outputLatency??0));
}
