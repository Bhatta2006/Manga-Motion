import {Container,Sprite,Texture,Rectangle} from 'pixi.js';
import {bytesHash} from './contract-v2.js';
import {layerPose} from './layer-pose.js';
import type {Panel,Page} from './script-types';
type Layer=NonNullable<Panel['layers']>[number];
export class CharacterLayers {
  readonly container=new Container();failures:string[]=[];private generation=0;
  private planes:{layer:Layer;group:Container;crop:Texture;mask:Texture;bitmap:ImageBitmap;base:Texture}[]=[];
  private verifiedSources=new Map<string,string>();
  async prepare(texture:Texture,page:Page,panel:Panel,base:string){
    this.destroy();this.failures=[];const token=this.generation;
    if(!panel.layers?.length)return true;
    try{
      const url=base+page.image;let digest=this.verifiedSources.get(url);
      if(!digest){const response=await fetch(url);if(!response.ok)throw Error('Original layer source unavailable');digest=await bytesHash(await response.arrayBuffer());this.verifiedSources.set(url,digest);}
      for(const layer of [...panel.layers].sort((a,b)=>a.depth-b.depth)){
        let bitmap:ImageBitmap|null=null,crop:Texture|null=null,mask:Texture|null=null,group:Container|null=null;
        try{
          if(digest!==layer.safety.source_sha256)throw Error('Original layer source hash mismatch');
          const response=await fetch(base+layer.mask);if(!response.ok)throw Error('Character mask unavailable');const bytes=await response.arrayBuffer();
          if(await bytesHash(bytes)!==layer.safety.mask_sha256)throw Error('Character mask hash mismatch');
          bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}));
          const [x,y,r,b]=layer.source_bbox;
          if(bitmap.width!==r-x||bitmap.height!==b-y)throw Error('Character mask dimensions differ from original source crop');
          if(token!==this.generation){bitmap.close();return false;}
          crop=new Texture({source:texture.source,frame:new Rectangle(x,y,r-x,b-y)});mask=Texture.from(bitmap);
          const sprite=new Sprite(crop),maskSprite=new Sprite(mask);sprite.anchor.set(...layer.anchor);maskSprite.anchor.set(...layer.anchor);
          // Pinned Pixi 8.21 alpha channel explicitly ignores PNG mask RGB.
          sprite.setMask({mask:maskSprite,channel:'alpha'});group=new Container();group.addChild(sprite,maskSprite);this.container.addChild(group);
          this.planes.push({layer,group,crop,mask,bitmap,base:texture});
        }catch(e){group?.destroy({children:true});crop?.destroy(false);mask?.destroy(true);bitmap?.close();if(token===this.generation)this.failures.push(`${layer.id}: ${String(e)}; showing original flat art.`);}
      }
    }catch(e){if(token===this.generation)this.failures.push(String(e)+'; showing original flat art.');}
    return token===this.generation;
  }
  update(u:number,panel:Panel,enabled:boolean){
    this.container.visible=enabled;
    for(const {layer,group} of this.planes){const [x,y,r,b]=layer.source_bbox,p=layerPose(layer,u);group.scale.set(p.scale);group.position.set(x+layer.anchor[0]*(r-x)+p.offset[0]*(panel.bbox[2]-panel.bbox[0]),y+layer.anchor[1]*(b-y)+p.offset[1]*(panel.bbox[3]-panel.bbox[1]));}
  }
  diagnostics(){return {characterLayers:this.planes.length,characterLayerVisible:this.container.visible&&this.planes.length>0,layerOriginalTextureShared:this.planes.every(p=>(p.group.children[0] as Sprite).texture.source===p.base.source),layerPoses:this.planes.map(p=>({id:p.layer.id,scale:p.group.scale.x,position:[p.group.position.x,p.group.position.y]}))};}
  destroy(){++this.generation;for(const p of this.planes){p.group.destroy({children:true});p.crop.destroy(false);p.mask.destroy(true);p.bitmap.close();}this.planes=[];}
}
