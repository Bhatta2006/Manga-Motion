import './style.css';
import {playback} from './api';

async function boot(){
  const params=new URLSearchParams(location.search);
  const series=params.get('series'),chapter=params.get('chapter');
  if(series&&chapter){
    const info=await playback(series,chapter);
    const {startReader}=await import('./reader');
    await startReader({scriptUrl:info.script_url,assetBase:info.asset_base,title:`${series} / ${chapter}`,library:true,series,chapter,readingWpm:info.reading_wpm});return;
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
