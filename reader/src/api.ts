export interface Job {id:string;series:string;chapter:string;status:'queued'|'running'|'failed'|'completed';phase:string;error:string|null;attempts:number;progress:{completed?:number;total?:number;state?:string}}
export interface Chapter {series:string;chapter:string;pages:number;playable:boolean;status:string;job:Job|null;review_flags:number}
export interface Playback {script_url:string;asset_base:string;snapshot:string;pages:number;panels:number}
export async function request<T>(url:string,body?:unknown):Promise<T>{
  const response=await fetch(url,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`);return data as T;
}
export const chapters=()=>request<{chapters:Chapter[];worker_error?:string|null}>('/api/library');
export const retryJob=(id:string)=>request<Job>(`/api/jobs/${encodeURIComponent(id)}/retry`,{});
export const playback=(series:string,chapter:string)=>request<Playback>(`/api/chapters/${encodeURIComponent(series)}/${encodeURIComponent(chapter)}/playback`);
