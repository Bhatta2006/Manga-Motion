/** Capture on the common stage parent so Flow and canvas share hold/replay. */
export class ReaderGestures {
  private points=new Map<number,{x:number;y:number;sx:number;sy:number}>();
  private timer=0;private consumed=false;private multiple=false;private began=0;private suppressClickUntil=0;
  private controller=new AbortController();
  constructor(parent:HTMLElement,hold:(x:number,y:number)=>void,replay:()=>void,interrupt:()=>void){
    const options={capture:true,signal:this.controller.signal};
    parent.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      if(!this.points.size)this.suppressClickUntil=0;
      this.points.set(e.pointerId,{x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY});
      if(this.points.size===1){this.consumed=false;this.multiple=false;this.began=performance.now();this.timer=window.setTimeout(()=>{if(this.points.size===1){this.consumed=true;interrupt();hold(e.clientX,e.clientY);}},520);}
      else{clearTimeout(this.timer);this.multiple=true;this.consumed=true;interrupt();e.preventDefault();e.stopImmediatePropagation();}
    },options);
    window.addEventListener('pointermove',e=>{const p=this.points.get(e.pointerId);if(p){p.x=e.clientX;p.y=e.clientY;if(Math.hypot(p.x-p.sx,p.y-p.sy)>10){clearTimeout(this.timer);this.began=0;}}
      if(this.consumed){e.preventDefault();e.stopImmediatePropagation();}},options);
    const finish=(e:PointerEvent)=>{const p=this.points.get(e.pointerId);if(!p)return;clearTimeout(this.timer);this.points.delete(e.pointerId);
      if(this.consumed){this.suppressClickUntil=performance.now()+600;e.preventDefault();e.stopImmediatePropagation();
        if(!this.points.size){interrupt();if(e.type==='pointerup'&&this.multiple&&this.began&&performance.now()-this.began<350&&p&&Math.hypot(e.clientX-p.sx,e.clientY-p.sy)<10)replay();this.multiple=false;}}
    };
    window.addEventListener('pointerup',finish,options);window.addEventListener('pointercancel',e=>{if(this.points.has(e.pointerId)){this.began=0;finish(e);}},options);
    parent.addEventListener('click',e=>{if(performance.now()<this.suppressClickUntil){e.preventDefault();e.stopImmediatePropagation();}},options);
    parent.addEventListener('contextmenu',e=>{e.preventDefault();},options);
    window.addEventListener('blur',()=>this.cancel(),{signal:this.controller.signal});
  }
  cancel(){clearTimeout(this.timer);this.points.clear();this.began=0;this.multiple=false;}
  destroy(){this.cancel();this.controller.abort();}
}
