import { Rectangle, Sprite, Texture } from 'pixi.js';
import { poseOf } from './core.js';
import type { Panel, Rect } from './script-types';

export class SourcePlane {
  sprite:Sprite|null=null;
  box:Rect|null=null;
  prepare(texture:Texture,panel:Panel) {
    this.destroy();
    const focus=panel.director.focus.find(f=>f.kind==='region'&&f.ref==='parallax-safe');
    if (!focus) return;
    this.box=focus.bbox;
    const [x0,y0,x1,y1]=this.box;
    // Shares the original page TextureSource; creates no painted/inpainted asset.
    this.sprite=new Sprite(new Texture({source:texture.source,frame:new Rectangle(x0,y0,x1-x0,y1-y0)}));
    this.sprite.anchor.set(.5);
  }
  update(phase:number,enabled:boolean) {
    if (!this.sprite||!this.box) return;
    this.sprite.visible=enabled;
    const p=poseOf(this.box,phase);
    this.sprite.scale.set(p.scale);
    this.sprite.position.set((this.box[0]+this.box[2])/2+p.dx,(this.box[1]+this.box[3])/2+p.dy);
  }
  destroy() { this.sprite?.destroy({texture:true,textureSource:false});this.sprite=null;this.box=null; }
}
