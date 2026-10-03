export function layerPose(layer,u){
  u=Math.max(0,Math.min(1,u));const poses=layer.poses;let a=poses[0],b=poses.at(-1);
  for(let i=1;i<poses.length;i++)if(u<=poses[i].u){a=poses[i-1];b=poses[i];break;}
  const t=Math.max(0,Math.min(1,(u-a.u)/(b.u-a.u)));
  return {scale:a.scale+(b.scale-a.scale)*t,offset:a.offset.map((v,i)=>v+(b.offset[i]-v)*t)};
}
