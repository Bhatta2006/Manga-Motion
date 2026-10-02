import {Graphics} from 'pixi.js';
import type {Rect} from './script-types';
/** An independent outline; never writes to the source texture or fills text. */
export class BubbleOverlay {
  readonly graphic=new Graphics();
  private key='';
  update(bbox:Rect|null,time:number,scale:number,reduce:boolean){
    this.graphic.visible=!!bbox;if(!bbox)return;
    const width=2/Math.max(.001,scale),key=[...bbox,width].join(',');
    if(key!==this.key){this.key=key;this.graphic.clear();const [x,y,r,b]=bbox;
      this.graphic.roundRect(x-width*3,y-width*3,r-x+width*6,b-y+width*6,width*4).stroke({color:0xbce2c9,width:width*5,alpha:.18});
      this.graphic.roundRect(x-width*3,y-width*3,r-x+width*6,b-y+width*6,width*4).stroke({color:0xbce2c9,width,alpha:.9});}
    this.graphic.alpha=reduce?1:.83+.17*Math.cos(time*2);
  }
}
