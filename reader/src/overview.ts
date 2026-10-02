import {Graphics} from 'pixi.js';
import type {Rect} from './script-types';
export class PageOverview {
  readonly graphic=new Graphics();
  update(bbox:Rect,scale:number,visible:boolean){
    this.graphic.visible=visible;if(!visible)return;
    const [x,y,r,b]=bbox;this.graphic.clear().rect(x,y,r-x,b-y).stroke({color:0xbce2c9,width:3/Math.max(.001,scale)});
  }
}
