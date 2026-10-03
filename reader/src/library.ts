import {chapters,request,retryJob,type Chapter,type Job} from './api';
const phaseNames:Record<string,string>={queued:'Waiting',starting:'Starting',import:'Importing pages',analysis:'Preparing analysis','magiv3-detection':'Finding panels','vision-normalize':'Ordering panels','baberu-ocr':'Reading text','vision-text-metadata':'Preparing text metadata',director:'Understanding scenes','local-director':'Understanding scenes','camera-solver':'Preparing camera motion',camera:'Preparing camera motion',publishing:'Preparing playback',completed:'Ready to read',interrupted:'Resuming cached work'};

export async function startLibrary(){
  phaseNames['scene-sfx']='Preparing scene sounds';
  phaseNames['scene-music']='Preparing background music';
  const root=document.querySelector('#app')!;root.classList.add('library-app');
  root.innerHTML=`<header><div class="brand">MangaMotion <span>/ Library</span></div><div class="study">Original art · local processing</div></header>
  <main class="library-main"><section class="library-intro"><p class="eyebrow">Your reading room</p><h1>Bring the page to life.</h1><p>Import a chapter, then follow its panels with camera motion.</p></section>
  <details class="import-box"><summary>Import a chapter</summary><form id="import-form">
  <label class="wide">Folder, CBZ, ZIP or PDF on D:<input name="source" id="source" required placeholder="D:\\Manga\\chapter-01" autocomplete="off"></label>
  <label>Series<input name="series" required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,63}" maxlength="64" placeholder="my-series"></label>
  <label>Chapter<input name="chapter" required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,63}" maxlength="64" placeholder="chapter-01"></label>
  <label>Reading direction<select name="direction"><option value="rtl">Right to left</option><option value="ltr">Left to right</option></select></label>
  <button class="primary" id="import-submit">Import &amp; process</button><p class="form-note wide">English text is supported in this build. Processing runs one chapter at a time.</p></form><p id="import-message" role="status"></p></details>
  <div class="library-heading"><h2>Chapters</h2><span id="library-count"></span></div><p id="library-error" role="status"></p><div id="chapter-list" class="chapter-list" aria-live="polite"></div></main>`;
  const list=document.getElementById('chapter-list')!,error=document.getElementById('library-error')!;
  let timer:number|undefined,stopped=false,rendered='';
  let offline=false;
  window.addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);},{once:true});
  function card(chapter:Chapter){
    const article=document.createElement('article');article.className='chapter-card';article.dataset.series=chapter.series;article.dataset.chapter=chapter.chapter;
    const eyebrow=document.createElement('p');eyebrow.className='eyebrow';eyebrow.textContent=chapter.series;
    const title=document.createElement('h3');title.textContent=chapter.chapter;
    const status=document.createElement('p');status.className=`chapter-status ${chapter.status}`;const job=chapter.job,p=job?.progress;
    status.textContent=chapter.status==='failed'?'Processing failed':job?phaseNames[job.phase]??job.phase:chapter.playable?'Ready to read':'Imported';
    if(chapter.status==='running'&&p?.total)status.textContent+=` · ${p.completed??0}/${p.total} pages${p.state?' · '+p.state:''}`;
    const meta=document.createElement('p');meta.className='chapter-meta';meta.textContent=`${chapter.partial?`${chapter.ready_pages}/${chapter.total_pages} pages ready`:`${chapter.pages} pages`}${chapter.review_flags?' · '+chapter.review_flags+' review notes':''}`;article.append(eyebrow,title,status,meta);
    const actions=document.createElement('div');actions.className='chapter-actions';
    if(chapter.semantic_review_pages){const note=document.createElement('p');note.className='chapter-meta';note.textContent=`Scene interpretation needs review on ${chapter.semantic_review_pages} pages.`;article.append(note);}
    if(chapter.playable){const read=document.createElement('a');read.className='read-link';read.textContent=chapter.partial?'Read ready pages':chapter.status==='completed'?'Read chapter':'Read saved version';read.href='/?'+new URLSearchParams({series:chapter.series,chapter:chapter.chapter});actions.append(read);}
    if(chapter.status==='failed'&&job){
      const message=document.createElement('p');message.className='job-error';message.textContent=job.error??'Unknown processing error';article.append(message);
      const retry=document.createElement('button');retry.textContent='Retry processing';retry.onclick=async()=>{retry.disabled=true;try{await retryJob(job.id);rendered='';await refresh();}catch(e){error.textContent=String(e);retry.disabled=false;}};actions.append(retry);
    }
    if(chapter.playable&&!offline){const review=document.createElement('a');review.className='review-link';review.textContent='Review';review.href='/?'+new URLSearchParams({series:chapter.series,chapter:chapter.chapter,review:'1'});actions.append(review);}
    article.append(actions);return article;
  }
  async function refresh(){
    clearTimeout(timer);
    try{const data=await chapters();offline=!!data.offline;(document.getElementById('import-submit') as HTMLButtonElement).disabled=offline;error.textContent=offline?'Offline · saved chapters only':data.worker_error?`Processing service needs attention: ${data.worker_error}`:'';const digest=JSON.stringify([offline,data.chapters]);if(digest!==rendered){rendered=digest;list.replaceChildren(...data.chapters.map(card));if(!data.chapters.length){const empty=document.createElement('p');empty.className='empty-library';empty.textContent='Your Library is empty. Import your first chapter above.';list.append(empty);}document.getElementById('library-count')!.textContent=`${data.chapters.length} chapters`;}}
    catch(e){error.textContent=`Could not refresh Library: ${String(e)}`;}
    if(!stopped)timer=window.setTimeout(()=>void refresh(),2000);
  }
  const form=document.getElementById('import-form') as HTMLFormElement;
  form.onsubmit=async event=>{
    event.preventDefault();const button=document.getElementById('import-submit') as HTMLButtonElement,message=document.getElementById('import-message')!;button.disabled=true;message.textContent='Queuing chapter…';
    try{const data=new FormData(form);const job=await request<Job>('/api/imports',{source:data.get('source'),series:data.get('series'),chapter:data.get('chapter'),direction:data.get('direction')});message.textContent=`${job.series} / ${job.chapter} queued. You can keep reading while it processes.`;await refresh();}catch(e){message.textContent=String(e);}finally{button.disabled=false;}
  };await refresh();
}
