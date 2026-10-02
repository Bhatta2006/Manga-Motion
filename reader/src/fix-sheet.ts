import {request} from './api';
import {pruneCorrections,textFields,reviewUrl} from './review-data';
import type {Review,ReviewPage,ReviewText} from './review-data';
export class FixSheet {
  readonly dialog=document.createElement('dialog');private saving=false;
  constructor(private series:string,private chapter:string){this.dialog.className='fix-sheet';this.dialog.setAttribute('aria-label','Fix selected bubble');document.body.append(this.dialog);this.dialog.addEventListener('cancel',e=>{if(this.saving)e.preventDefault();});}
  open(data:Review,page:ReviewPage,text:ReviewText,panelId:string){
    if(this.dialog.open||this.saving)return;this.dialog.replaceChildren();
    const heading=document.createElement('h2');heading.textContent='Fix bubble · '+text.id;
    const note=document.createElement('p');note.textContent='Text and speaker fixes update the saved chapter. Emotion and re-voice will be available when voices are implemented.';
    const crop=document.createElementNS('http://www.w3.org/2000/svg','svg'),image=document.createElementNS(crop.namespaceURI,'image');
    crop.classList.add('review-crop');crop.setAttribute('viewBox',`${text.bbox[0]} ${text.bbox[1]} ${text.bbox[2]-text.bbox[0]} ${text.bbox[3]-text.bbox[1]}`);crop.setAttribute('role','img');crop.setAttribute('aria-label','Selected original bubble');
    image.setAttribute('href',reviewUrl(this.series,this.chapter)+'/pages/'+page.page_sha256);image.setAttribute('width',String(page.size[0]));image.setAttribute('height',String(page.size[1]));crop.append(image);
    const form=document.createElement('form'),apply=textFields(form,text,page,data.corrections),message=document.createElement('p');message.id='fix-message';message.setAttribute('role','status');
    const save=document.createElement('button');save.type='submit';save.className='primary';save.id='fix-save';save.textContent='Save and return to this scene';
    const close=document.createElement('button');close.type='button';close.id='fix-close';close.textContent='Cancel';close.onclick=()=>this.dialog.close();
    const review=document.createElement('a');review.textContent='Full chapter review';review.href='/?'+new URLSearchParams({series:this.series,chapter:this.chapter,review:'1'});
    form.append(save,close);this.dialog.append(heading,note,crop,form,message,review);this.dialog.showModal();
    form.onsubmit=e=>{e.preventDefault();if(this.saving)return;const candidate=structuredClone(data.corrections);apply(candidate);pruneCorrections(candidate);this.saving=true;form.inert=true;form.setAttribute('aria-busy','true');message.textContent='Saving and updating this chapter…';
      void request<Review>(reviewUrl(this.series,this.chapter),{expected_revision:data.revision,corrections:candidate}).then(()=>{
        location.assign('/?'+new URLSearchParams({series:this.series,chapter:this.chapter,at:panelId}));
      }).catch(e=>{message.textContent=String(e)+' Your edits are retained. Cancel and reopen to load the latest saved revision.';}).finally(()=>{this.saving=false;form.inert=false;form.removeAttribute('aria-busy');});
    };
  }
}
