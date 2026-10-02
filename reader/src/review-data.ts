import type {CorrectionsV1,VCorrectionsText,VCorrectionsPanel} from './generated/motionscript';
import correctionSchema from '../../schema/corrections-v1.schema.json';
import type {Rect} from './script-types';
export interface ReviewText {id:string;text:string;kind:NonNullable<VCorrectionsText['kind']>;panel_id:string|null;bbox:Rect;speaker:string|null}
export interface ReviewScene {beat:NonNullable<VCorrectionsPanel['beat']>;mood:string[];energy:number;time_skip:boolean}
export interface ReviewPage {id:string;page_sha256:string;geometry_sha256:string;size:[number,number];order:string[];texts:ReviewText[];panels:{id:string;bbox:Rect}[];scenes:Record<string,ReviewScene>}
export interface ReviewIssue {id:string;page_sha256:string;kind:string;target:string;bbox:Rect;reasons:string[]}
export interface Review {corrections:CorrectionsV1;revision:string;pages:ReviewPage[];issues:ReviewIssue[];unresolved:number;confidence_note:string;elapsed_seconds?:number}
export const reviewUrl=(series:string,chapter:string)=>`/api/chapters/${encodeURIComponent(series)}/${encodeURIComponent(chapter)}/review`;
export function pruneCorrections(candidate:CorrectionsV1){
  for(const [digest,p] of Object.entries(candidate.pages))if(!p.order&&!p.order_confirmed&&!Object.keys(p.texts??{}).length&&!Object.keys(p.panels??{}).length)delete candidate.pages[digest];
  return candidate;
}
/** Both correction surfaces build the same schema-derived, source-bound patch. */
export function textFields(form:HTMLFormElement,text:ReviewText,page:ReviewPage,corrections:CorrectionsV1){
  function label<T extends HTMLElement>(name:string,field:T){const label=document.createElement('label');label.textContent=name;label.append(field);form.append(label);return field;}
  function select(id:string,values:string[],value:string){const s=document.createElement('select');s.id=id;for(const v of values)s.add(new Option(v,v));s.value=value;return s;}
  const area=document.createElement('textarea');area.id='fix-text';area.rows=4;area.maxLength=4000;area.value=text.text;label('Text',area);
  const kind=label('Text kind',select('fix-kind',correctionSchema.definitions.text.properties.kind.enum,text.kind));
  const panel=label('Belongs to panel',select('fix-panel',['unassigned',...page.order],text.panel_id??'unassigned'));
  const speaker=document.createElement('input');speaker.id='fix-speaker';speaker.value=text.speaker??'';speaker.maxLength=64;speaker.pattern='[A-Za-z0-9][A-Za-z0-9_-]{0,63}';label('Speaker ID (optional; voices pending)',speaker);
  const confirm=document.createElement('input');confirm.id='fix-confirm';confirm.type='checkbox';confirm.checked=corrections.pages[page.page_sha256]?.texts?.[text.id]?.confirmed??false;label('I checked this text against the original',confirm);
  return (fix:CorrectionsV1)=>{const p=fix.pages[page.page_sha256]??={geometry_sha256:page.geometry_sha256};(p.texts??={})[text.id]={text:area.value,kind:kind.value as ReviewText['kind'],panel_id:panel.value==='unassigned'?null:panel.value,speaker:speaker.value||null,confirmed:confirm.checked};};
}
