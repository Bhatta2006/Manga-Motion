export type Rect = [number, number, number, number];
export type CameraEvent = {type:'camera';t:number;dur:number;move:'push_in'|'pull_out'|'pan'|'hold';from:Rect;to:Rect;ease:'linear'|'outQuad'|'inOutSine'};
export type LineEvent = {type:'line';t:number;dur:number;bubble:string;speaker:string;text:string;audio:string;emotion:{delivery:'speak'|'shout'|'whisper'|'think'|'narrate'|'cry'|'laugh';intensity:number};highlight:boolean};
export type SfxEvent = {type:'sfx';t:number;file:string;gain_db:number};
export type Focus = {kind:'face'|'object'|'bubble'|'region';ref?:string;char?:string;bbox:Rect};
export type Panel = {id:string;bbox:Rect;director:{beat:'establish'|'dialogue'|'reaction'|'reveal'|'impact'|'chase'|'comedy'|'flashback'|'quiet'|'transition';shot:'wide'|'medium'|'closeup'|'extreme_closeup'|'splash'|'insert';energy:number;mood:string[];time_skip:boolean;focus:Focus[]};timeline:(CameraEvent|LineEvent|SfxEvent)[];transition_out:{type:'glide'|'cut'|'fade'|'whip'|'dissolve'|'dip';dur:number};confidence:{panel:number|null;ocr:number|null;speaker:number|null}};
export type Page = {id:string;image:string;size:[number,number];panels:Panel[]};
export type MotionScript = {version:1;chapter:string;direction:'rtl'|'ltr';characters:Record<string,{voice:string;name?:string}>;pages:Page[]};
