export type Rect = [number, number, number, number];
export type CameraEvent = {type:'camera';t:number;dur:number;move:string;from:Rect;to:Rect;ease:string};
export type LineEvent = {type:'line';t:number;dur:number;bubble:string;speaker:string;text:string;audio:string;emotion:{delivery:string;intensity:number};highlight:boolean};
export type SfxEvent = {type:'sfx';t:number;file:string;gain_db:number};
export type Panel = {id:string;bbox:Rect;director:{beat:string;shot:string;energy:number;mood:string[];time_skip:boolean;focus:{kind:string;ref?:string;char?:string;bbox:Rect}[]};timeline:(CameraEvent|LineEvent|SfxEvent)[];transition_out:{type:string;dur:number};confidence:Record<string,number|null>};
export type Page = {id:string;image:string;size:[number,number];panels:Panel[]};
export type MotionScript = {version:1;chapter:string;direction:'rtl'|'ltr';characters:Record<string,{voice:string;name?:string}>;pages:Page[]};
