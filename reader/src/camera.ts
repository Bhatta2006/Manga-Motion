import { Container } from 'pixi.js';
import type { Rect } from './types';

export function fit(container:Container,rect:Rect,width:number,height:number) {
  const scale=Math.min(width/(rect[2]-rect[0]),height/(rect[3]-rect[1]));
  container.scale.set(scale);
  container.position.set(width/2-(rect[0]+rect[2])/2*scale,height/2-(rect[1]+rect[3])/2*scale);
  return {width:(rect[2]-rect[0])*scale,height:(rect[3]-rect[1])*scale};
}
