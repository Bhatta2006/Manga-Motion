import './style.css';
import {playback} from './api';

async function boot(){
  const params=new URLSearchParams(location.search);
  const series=params.get('series'),chapter=params.get('chapter');
  if(series&&chapter){
    if(params.has('review')){const {startReview}=await import('./review');await startReview(series,chapter);return;}
    const info=await playback(series,chapter);
    const snapshot=params.get('snapshot');
    if(snapshot){
      if(!/^[a-f0-9]{64}$/.test(snapshot))throw Error('Invalid comparison snapshot');
      const base=`/api/chapters/${encodeURIComponent(series)}/${encodeURIComponent(chapter)}/playback/${snapshot}`;
      info.script_url=base+'/motionscript.json';info.asset_base=base+'/assets/';info.partial=false;
    }
    const {startReader}=await import('./reader');
    await startReader({scriptUrl:info.script_url,assetBase:info.asset_base,title:params.has('comparison')?'Comparison sample':`${series} / ${chapter}`,library:true,series,chapter,readingWpm:info.reading_wpm,partial:info.partial,totalPages:info.total_pages,comparison:params.has('comparison'),startPanel:params.get('at')??undefined});return;
  }
  const health=await fetch('/api/health');
  if(health.status===404){
    const {startReader}=await import('./reader');
    await startReader({scriptUrl:'/chapter/motionscript.json',assetBase:'/chapter/',title:'Motion study'});
  }else{
    if(!health.ok)throw Error('Library service is unavailable');
    const {startLibrary}=await import('./library');await startLibrary();
  }
}
boot().catch(error=>{
  const root=document.querySelector('#app')!;root.replaceChildren();const main=document.createElement('main');main.className='fatal';
  const message=document.createElement('p');message.setAttribute('role','alert');message.textContent=String(error);
  const back=document.createElement('a');back.href='/';back.textContent='Return to Library';
  const retry=document.createElement('button');retry.textContent='Retry';retry.onclick=()=>location.reload();
  main.append(message,back,retry);root.append(main);
});
