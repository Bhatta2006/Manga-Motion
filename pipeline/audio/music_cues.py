"""Inspectable conservative mood selection with causal scene continuity."""
import copy
import re
from pipeline.ingest.hashes import object_hash

REVISION='mood-scene-map-1'
GROUPS=[('tense',{'tense','ominous','fear','fearful','anxious','panic','alarmed'}),
        ('sad',{'sad','melancholic','regret','grief','somber'}),
        ('action',{'determined','urgent','aggressive','intense'}),
        ('mystery',{'mysterious','curious','suspenseful'}),
        ('bright',{'playful','happy','joyful','excited','energetic','amused'}),
        ('warm',{'caring','warm','nostalgic','tender','hopeful'}),
        ('calm',{'calm','peaceful','neutral','thoughtful'})]

def profile(tags):
    moods={m.lower() for m in tags.get('mood',[])}
    for key,group in GROUPS:
        if moods&group:return key
    if tags.get('beat') in ('impact','chase') and tags.get('energy',0)>=.6:return 'action'
    return None

def cues(record,previous=None):
    state=copy.deepcopy(previous or {'scene':None,'profile':None,'ambience':None,'pending':None,'count':0})
    semantics=record.get('semantics',{})
    tags={p['id']:p for p in semantics.get('panels',[])}
    summary=semantics.get('summary','').lower()
    atmosphere='rain' if re.search(r'\b(rain|rainy|raining|downpour)\b',summary) else 'wind' if re.search(r'\b(grassy field|forest|sea|ship|beach|mountain|wind|snow)\b',summary) else None
    assignments=[];new_scenes={};reviews=[]
    for panel_id in record['order']['panel_ids']:
        tag=tags.get(panel_id,{})
        requested=profile(tag)
        reason='mood_tags' if requested else 'uncertain_keep_previous' if state['profile'] else 'unknown_silent'
        # Two consecutive changed mood cues earn a music change; time skips reset immediately.
        if requested and requested!=state['profile']:
            state['count']=state['count']+1 if state['pending']==requested else 1;state['pending']=requested
        else:state['pending']=None;state['count']=0
        change=bool(requested and (state['profile'] is None or tag.get('time_skip') or state['count']>=2))
        selected=requested if change else state['profile']
        if requested and requested!=selected:reason='transient_mood_keeps_scene'
        atmosphere_change=state['ambience']!=atmosphere
        if tag.get('time_skip') and requested is None:selected=None;reason='unknown_time_skip_silent'
        if change or atmosphere_change or tag.get('time_skip'):
            state.update(profile=selected,ambience=atmosphere,pending=None,count=0)
            state['scene']='scene_'+object_hash({'page':record['id'],'panel':panel_id,'profile':selected,'ambience':atmosphere})[:16] if selected or atmosphere else None
            if state['scene']:new_scenes[state['scene']]={'profile':selected,'ambience':atmosphere,'mood':tag.get('mood',[])[:8]}
        assignment={'panel_id':panel_id,'scene':state['scene'],'requested_profile':requested,'selected_profile':selected,
                    'reason':reason,'needs_review':True}
        assignments.append(assignment)
        reviews.append({'panel_id':panel_id,'reason':'music_semantics_unverified' if requested else reason})
    return {'assignments':assignments,'new_scenes':new_scenes,'state':state,'review':reviews}
