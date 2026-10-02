import type {Panel} from './types';
export function duckPoints(panel:Panel,durations?:Record<string,number>,transition?:number):[number,number][];
export function gainAt(points:[number,number][],time:number):number;
export function scheduleDuck(param:AudioParam,points:[number,number][],offset:number,now:number):void;
