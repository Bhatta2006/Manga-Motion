import {request} from './api';
import type {CorrectionsV1} from './generated/motionscript';
import correctionSchema from '../../schema/corrections-v1.schema.json';
import type {Rect} from './script-types';
import {textFields,pruneCorrections} from './review-data';
import type {Review,ReviewScene as Scene} from './review-data';
export async function startReview(series:string,chapter:string){
  const url=`/api/chapters/${encodeURIComponent(series)}/${encodeURIComponent(chapter)}/review`,root=document.querySelector('#app')!;
  root.classList.add('library-app');root.innerHTML='<header><div class="brand">MangaMotion <span>/ Review</span></div><a class="library-link" href="/">Library</a></header><main class="review-main"><div class="review-heading"><h1>Review chapter</h1><a id="review-read" class="read-link">Read chapter</a></div><p id="review-count" role="status"></p><p class="review-note">Confirm uncertain text and scenes, or correct them below. Saved fixes are reused on future processing. Voices are pending; speaker assignments are saved for that stage.</p><div class="review-toolbar"><label>Page <select id="review-page"></select></label><button id="review-reload">Reload saved review</button></div><div class="review-grid"><section><h2>Review notes</h2><div id="review-issues"></div></section><section id="review-editor" aria-label="Correction editor"></section></div><p id="review-message" role="status"></p></main>';
  const $=<T extends HTMLElement>(id:string)=>document.getElementById(id)! as T;
  const read=$('review-read') as HTMLAnchorElement;read.href='/?'+new URLSearchParams({series,chapter});
  let data:Review,pageIndex=0,saving=false;
  const page=()=>data.pages[pageIndex];
  function crop(bbox:Rect){
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),image=document.createElementNS(svg.namespaceURI,'image');
    svg.setAttribute('viewBox',`${bbox[0]} ${bbox[1]} ${bbox[2]-bbox[0]} ${bbox[3]-bbox[1]}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','Original art crop');svg.classList.add('review-crop');
    image.setAttribute('href',url+'/pages/'+page().page_sha256);image.setAttribute('width',String(page().size[0]));image.setAttribute('height',String(page().size[1]));svg.append(image);return svg;
  }
  function feedback(message:string){$('review-message').textContent=message;}
  async function save(candidate:CorrectionsV1,kind:string,target:string){
    pruneCorrections(candidate);
    if(saving)return;saving=true;const form=$('review-form');form.inert=true;form.setAttribute('aria-busy','true');($('review-page') as HTMLSelectElement).disabled=true;($('review-reload') as HTMLButtonElement).disabled=true;feedback('Saving and updating this chapter…');
    try{data=await request<Review>(url,{expected_revision:data.revision,corrections:candidate});renderList();edit(kind,target);feedback(`Saved. Playback updated in ${data.elapsed_seconds?.toFixed(2)} s. Original art and OCR caches retained.`);}
    catch(e){feedback(String(e)+' Your edits are still shown; reload only if another window changed the saved version.');}
    finally{saving=false;$('review-form').inert=false;$('review-form').removeAttribute('aria-busy');($('review-page') as HTMLSelectElement).disabled=false;($('review-reload') as HTMLButtonElement).disabled=false;}
  }
  function renderList(){
    $('review-count').textContent=`${series} / ${chapter} · ${data.unresolved} unresolved notes · ${data.confidence_note}`;
    const list=$('review-issues');list.replaceChildren();
    for(const issue of data.issues.filter(i=>i.page_sha256===page().page_sha256)){
      const button=document.createElement('button');button.className='review-issue';button.dataset.kind=issue.kind;button.dataset.target=issue.target;
      const title=document.createElement('strong');title.textContent=issue.kind+' · '+issue.target;
      const reason=document.createElement('span');reason.textContent=issue.reasons.join(', ').replaceAll('_',' ');button.append(crop(issue.bbox),title,reason);
      button.onclick=()=>{if(!saving){edit(issue.kind,issue.target);$('review-editor').scrollIntoView({block:'nearest',behavior:'instant'});}};list.append(button);
    }
    const order=document.createElement('button');order.id='review-order';order.textContent='Edit panel order';order.onclick=()=>edit('order','order');list.prepend(order);
    const texts=document.createElement('details'),summary=document.createElement('summary');summary.textContent='All text crops';texts.append(summary);
    for(const text of page().texts){const button=document.createElement('button');button.className='review-text-link';button.textContent=text.id+' · '+text.text;button.onclick=()=>edit('text',text.id);texts.append(button);}list.append(texts);
  }
  function edit(kind:string,target:string){
    const editor=$('review-editor');editor.replaceChildren();const title=document.createElement('h2');title.textContent=kind+' · '+target;editor.append(title);
    const form=document.createElement('form');form.id='review-form';editor.append(form);const digest=page().page_sha256;
    function label<T extends HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement>(text:string,input:T){const label=document.createElement('label');label.textContent=text;label.append(input);form.append(label);return input;}
    function input(id:string,value:string){const input=document.createElement('input');input.id=id;input.value=value;return input;}
    function select(id:string,values:string[],value:string){const select=document.createElement('select');select.id=id;for(const v of values)select.add(new Option(v,v));select.value=value;return select;}
    let apply:(fix:CorrectionsV1)=>void,revert:(fix:CorrectionsV1)=>void;
    const existing=data.corrections.pages[digest]??{geometry_sha256:page().geometry_sha256};
    if(kind==='text'||kind==='speaker'){
      const text=page().texts.find(t=>t.id===target);if(!text){feedback('Text target is unavailable.');return;}form.append(crop(text.bbox));
      apply=textFields(form,text,page(),data.corrections);
      revert=fix=>{delete fix.pages[digest]?.texts?.[target];};
    }else if(kind==='order'){
      form.append(crop([0,0,...page().size]));const order=page().order.slice(),list=document.createElement('ol');list.id='fix-order';form.append(list);
      const refresh=()=>{list.replaceChildren();order.forEach((id,i)=>{const item=document.createElement('li'),name=document.createElement('span');name.textContent=id;item.append(name);for(const [symbol,delta] of [['↑',-1],['↓',1]] as const){const button=document.createElement('button');button.type='button';button.textContent=symbol;button.setAttribute('aria-label',`Move ${id} ${delta<0?'earlier':'later'}`);button.disabled=i+delta<0||i+delta>=order.length;button.onclick=()=>{[order[i],order[i+delta]]=[order[i+delta],order[i]];refresh();};item.append(button);}list.append(item);});};refresh();
      apply=fix=>{const p=fix.pages[digest]??={geometry_sha256:page().geometry_sha256};p.order=order;p.order_confirmed=true;};revert=fix=>{delete fix.pages[digest]?.order;delete fix.pages[digest]?.order_confirmed;};
    }else{
      const panel=page().panels.find(p=>p.id===target),scene=page().scenes[target];form.append(crop(panel?.bbox??[0,0,...page().size]));
      if(!scene){const note=document.createElement('p');note.textContent='This note needs geometry or stage review. No automatic confirmation is offered.';form.append(note);return;}
      const beat=label('Scene beat',select('fix-beat',correctionSchema.definitions.panel.properties.beat.enum,scene.beat));
      const mood=label('Mood (up to three, comma separated)',input('fix-mood',scene.mood.join(', ')));
      const energy=label('Energy (0–1)',input('fix-energy',String(scene.energy)));energy.type='number';energy.min='0';energy.max='1';energy.step='.05';energy.required=true;
      const skip=input('fix-skip','');skip.type='checkbox';skip.checked=scene.time_skip;label('New scene / time skip',skip);
      const confirm=input('fix-confirm','');confirm.type='checkbox';confirm.checked=existing.panels?.[target]?.confirmed??false;label('I checked this scene interpretation',confirm);
      apply=fix=>{const p=fix.pages[digest]??={geometry_sha256:page().geometry_sha256};(p.panels??={})[target]={beat:beat.value as Scene['beat'],mood:mood.value.split(',').map(s=>s.trim()).filter(Boolean),energy:Number(energy.value),time_skip:skip.checked,confirmed:confirm.checked};};
      revert=fix=>{delete fix.pages[digest]?.panels?.[target];};
    }
    const saveButton=document.createElement('button');saveButton.type='submit';saveButton.className='primary';saveButton.id='fix-save';saveButton.textContent='Save correction';form.append(saveButton);
    const reset=document.createElement('button');reset.type='button';reset.id='fix-revert';reset.textContent='Use original result';reset.onclick=()=>{const fix=structuredClone(data.corrections);revert(fix);void save(fix,kind,target);};form.append(reset);
    form.onsubmit=event=>{event.preventDefault();const fix=structuredClone(data.corrections);apply(fix);void save(fix,kind,target);};
  }
  async function reload(){if(saving)return;data=await request<Review>(url);const selector=$('review-page') as HTMLSelectElement;selector.replaceChildren();data.pages.forEach((p,i)=>selector.add(new Option('Page '+(i+1),String(i))));pageIndex=Math.min(pageIndex,data.pages.length-1);selector.value=String(pageIndex);renderList();if(page().texts.length)edit('text',page().texts[0].id);}
  ($('review-page') as HTMLSelectElement).onchange=()=>{if(saving)return;pageIndex=Number(($('review-page') as HTMLSelectElement).value);renderList();if(page().texts.length)edit('text',page().texts[0].id);};
  $('review-reload').onclick=()=>void reload().catch(e=>feedback(String(e)));await reload();
}
