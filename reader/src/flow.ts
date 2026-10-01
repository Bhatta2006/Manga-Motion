/** Native vertical scrolling selects scenes; scene playback retains Web Audio time. */
export class FlowController {
  readonly rail=document.createElement('div');
  private current=0;
  private enabled=false;
  private dragging=false;
  private manual=false;
  private timer=0;
  private start:{x:number;y:number}|null=null;
  private tappedWhilePlaying=false;
  private observer:ResizeObserver;
  constructor(parent:HTMLElement,private count:number,private select:(index:number)=>void,
              private interrupt:()=>void,private tap:(wasPlaying:boolean)=>void,private isPlaying:()=>boolean){
    this.rail.className='flow-rail';this.rail.tabIndex=0;
    this.rail.setAttribute('role','region');this.rail.setAttribute('aria-label','Scene flow: swipe up for next, down for previous; tap to pause');
    parent.append(this.rail);this.rebuild();
    this.observer=new ResizeObserver(()=>{this.resize();});this.observer.observe(this.rail);
    this.rail.addEventListener('scroll',()=>{if(this.manual)this.schedule();},{passive:true});
    this.rail.addEventListener('wheel',()=>{this.begin();this.schedule();},{passive:true});
    this.rail.addEventListener('pointerdown',e=>{this.tappedWhilePlaying=this.isPlaying();this.dragging=true;this.start={x:e.clientX,y:e.clientY};this.begin();},{passive:true});
    this.rail.addEventListener('pointerup',e=>{
      const tapped=this.start&&Math.hypot(e.clientX-this.start.x,e.clientY-this.start.y)<8;
      this.dragging=false;this.start=null;
      if(tapped){this.manual=false;this.tap(this.tappedWhilePlaying);}else this.schedule();
    },{passive:true});
    this.rail.addEventListener('pointercancel',()=>{this.dragging=false;this.start=null;this.schedule();},{passive:true});
    this.rail.addEventListener('keydown',e=>{
      if(['ArrowDown','ArrowUp','PageDown','PageUp'].includes(e.key)){
        e.preventDefault();this.begin();this.choose(this.current+(['ArrowDown','PageDown'].includes(e.key)?1:-1));
      }else if(e.key===' '||e.key==='Enter'){e.preventDefault();const playing=this.isPlaying();this.interrupt();this.tap(playing);}
    });
    this.setEnabled(false);
  }
  private begin(){if(!this.enabled)return;clearTimeout(this.timer);this.manual=true;this.interrupt();}
  private schedule(){clearTimeout(this.timer);this.timer=window.setTimeout(()=>{
    if(this.dragging){this.schedule();return;}
    if(this.manual&&this.enabled)this.choose(Math.round(this.rail.scrollTop/Math.max(1,this.rail.clientHeight)));
  },160);}
  private choose(target:number){
    // A vigorous flick is one scene decision, not a silent jump over dialogue.
    const next=Math.max(0,Math.min(this.count-1,this.current+Math.sign(target-this.current)));
    const changed=next!==this.current;this.manual=false;this.sync(next);
    if(changed)this.select(next);
  }
  private rebuild(){
    this.rail.replaceChildren();
    for(let i=0;i<this.count;i++){const marker=document.createElement('div');marker.className='flow-stop';marker.setAttribute('aria-hidden','true');this.rail.append(marker);}
    this.resize();
  }
  private resize(){for(const node of Array.from(this.rail.children))(node as HTMLElement).style.height=this.rail.clientHeight+'px';this.sync(this.current);}
  setCount(count:number){this.count=count;this.rebuild();}
  setEnabled(value:boolean){this.enabled=value;this.rail.hidden=!value;this.manual=false;clearTimeout(this.timer);if(value)this.resize();}
  sync(index:number){this.current=index;this.manual=false;clearTimeout(this.timer);this.rail.scrollTo({top:index*this.rail.clientHeight,behavior:'instant'});}
  destroy(){clearTimeout(this.timer);this.observer.disconnect();this.rail.remove();}
}
