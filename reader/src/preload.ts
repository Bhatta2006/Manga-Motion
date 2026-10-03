/** One speculative load at a time; current acquisition shares in-flight work. */
export class WindowPrefetch<T>{
  readonly cache=new Map<string,T>();private pending=new Map<string,Promise<T>>();private wanted:string[]=[];private protected=new Set<string>();private running=false;private closed=false;
  constructor(private load:(key:string)=>Promise<T>,private release:(key:string,value:T)=>Promise<void>){ }
  async acquire(key:string,pin=true){
    if(pin)this.protected.add(key);
    const cached=this.cache.get(key);if(cached)return cached;
    let request=this.pending.get(key);
    if(!request){request=this.load(key).then(async value=>{if(this.closed){await this.release(key,value);throw Error('Prefetch closed');}this.cache.set(key,value);return value;}).finally(()=>this.pending.delete(key));this.pending.set(key,request);}
    return request;
  }
  select(keys:string[],protectedKeys:string[]=[]){this.wanted=[...new Set(keys)].slice(0,5);this.protected=new Set(protectedKeys);void this.pump();}
  private async evict(){for(const [key,value] of this.cache)if(!this.wanted.includes(key)&&!this.protected.has(key)){this.cache.delete(key);await this.release(key,value);}}
  private async pump(){
    if(this.running||this.closed)return;this.running=true;
    try{await this.evict();while(!this.closed){const next=this.wanted.find(key=>!this.cache.has(key)&&!this.pending.has(key));if(!next)break;try{await this.acquire(next,false);}catch{/* A speculative miss is retried visibly on navigation. */}await this.evict();if(!this.cache.has(next)&&this.wanted.includes(next))break;}}
    finally{this.running=false;}
  }
  async close(){this.closed=true;this.wanted=[];this.protected.clear();await this.evict();}
}
export function pageWindow<T extends {size:[number,number]}>(pages:T[],at:number,pixelBudget=32*2**20){
  const result=[at];let pixels=pages[at].size[0]*pages[at].size[1];
  for(const delta of [1,-1,2,-2]){const next=at+delta;if(next<0||next>=pages.length)continue;const size=pages[next].size[0]*pages[next].size[1];if(pixels+size<=pixelBudget){result.push(next);pixels+=size;}}
  return result;
}
