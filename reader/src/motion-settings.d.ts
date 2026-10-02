import type {Panel,Page,Rect} from './script-types';
export const MOTION_LEVELS:Record<string,number>;
export function styledCamera(panel:Panel,time:number,preset?:string,reduce?:boolean):Rect;
export function shakeEligible(page:Page,panel:Panel):boolean;
export function protectedShake(panel:Panel,rect:Rect):boolean;
export function sceneEffects(panel:Panel,time:number,preset?:string,reduce?:boolean,canShake?:boolean):{dx:number;dy:number;flash:number;vignette:number};
