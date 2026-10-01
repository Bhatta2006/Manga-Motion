"""Deterministic beat recipes using the existing v1 camera events."""
from dataclasses import dataclass
from pipeline.motion.solver import contains


@dataclass(frozen=True)
class Recipe:
    move: str
    seconds: float
    zoom: float
    transient: bool=False


TABLE={
    'establish':Recipe('pan',5,1.08),
    'dialogue':Recipe('hold',2,1),
    'reaction':Recipe('push_in',4,1.25),
    'reveal':Recipe('pull_out',3.5,1.25),
    'impact':Recipe('push_in',.18,1.35,True),
    'chase':Recipe('pan',2.5,1.05),
    'comedy':Recipe('push_in',1.5,1.18),
    'flashback':Recipe('pan',5,1.04),
    'quiet':Recipe('push_in',3,1.04),
    'transition':Recipe('hold',2,1),
}


def recipe(tags):
    value=TABLE[tags['beat']]
    if tags['beat']=='reaction' and tags['shot']=='extreme_closeup' and tags['energy']>=.8:
        return Recipe('push_in',.18,1.35,True)
    if tags['beat']=='impact' and tags['energy']<.5:return Recipe('hold',2,1)
    return value


def finish_motion(event,tags,protected=None):
    """Hit-stop and bounded comedy return, followed by the ordinary reading hold."""
    events=[event]
    if recipe(tags).transient and event['move']!='hold':
        events.append({'type':'camera','t':event['dur'],'move':'hold','from':event['to'],'to':event['to'],
                       'dur':2/60,'ease':'linear'})
        a=event['to'];w=(a[2]-a[0])/1.025;h=(a[3]-a[1])/1.025
        center=[(a[0]+a[2])/2,(a[1]+a[3])/2];end=[center[0]-w/2,center[1]-h/2,center[0]+w/2,center[1]+h/2]
        if protected is not None and contains(end,protected):
            events.append({'type':'camera','t':event['dur']+2/60,'move':'push_in','from':a,'to':end,'dur':2.5,'ease':'inOutSine'})
    if tags['beat']=='comedy' and event['move']!='hold':
        overshoot=event['to']
        settle=[v+(a-v)*.2 for v,a in zip(overshoot,event['from'])]
        event['dur']=1.1
        events.append({'type':'camera','t':1.1,'move':'pull_out','from':overshoot,'to':settle,'dur':.4,'ease':'inOutSine'})
    return events


def speaker_follow(master, lines, frames):
    """Future voice line starts are the timing authority, including overlaps.

    frames are already solved safe camera rectangles; missing/3+ speakers use
    the master. No inferred speech timing or identities are invented here.
    """
    many=len({line['speaker'] for line in lines})>=3
    output=[];current=master
    ordered=sorted(lines,key=lambda item:item['t'])
    for index,line in enumerate(ordered):
        target=master if many else frames.get(line['bubble'],master)
        start=line['t'];next_start=ordered[index+1]['t'] if index+1<len(ordered) else start+.4
        duration=min(.4,max(.001,next_start-start))
        output.append({'type':'camera','t':start,'move':'pan' if current!=target else 'hold',
                       'from':current,'to':target,'dur':duration,'ease':'inOutSine'})
        current=target
    return output
