"""Restrained, inspectable scene cues; no page-turn/fictional impact default."""
import re

CATEGORIES={'impact','whoosh','footsteps','door','heartbeat','rain','wind','chime'}
REVISION='scene-sfx-map-2'


def cues(record):
    texts={t['id']:t for t in record['texts']};ordered=record['order']['panel_ids']
    panels={p['id']:p for p in record.get('semantics',{}).get('panels',[])}
    output=[];review=[];accents=0;stylistic=set()
    summary=record.get('semantics',{}).get('summary','').lower()
    outside=bool(re.search(r'\b(grassy field|forest|sea|ship|beach|mountain|wind|snow)\b',summary))
    for index,panel_id in enumerate(ordered):
        tags=panels.get(panel_id)
        if not tags:continue
        selected=[]
        for cue in tags['sfx']:
            category=cue['category'];text_id=cue['text_id']
            if category=='none':continue
            if category not in CATEGORIES:raise ValueError('Unknown scene sound category')
            if text_id!='scene' and texts[text_id]['kind']!='sfx':
                review.append({'panel_id':panel_id,'reason':'sfx_cue_conflicts_with_text_class','text_id':text_id});continue
            selected.append({'category':category,'reason':'director_visible_scene' if text_id=='scene' else 'printed_sfx','text_id':text_id})
        if not selected:
            mood=set(tags['mood']);beat=tags['beat'];energy=tags['energy']
            if beat=='impact' and energy>=.5:selected=[{'category':'impact','reason':'impact_beat','text_id':None}]
            elif beat=='chase' and energy>=.5:selected=[{'category':'whoosh','reason':'chase_beat','text_id':None}]
            elif beat in ('reaction','reveal') and energy>=.65 and mood&{'tense','ominous','panic','fear','anxious'}:
                selected=[{'category':'heartbeat','reason':'dramatic_tension_accent','text_id':None}]
            elif beat in ('comedy','reaction') and energy>=.7 and mood&{'playful','energetic','excited'}:
                selected=[{'category':'chime','reason':'light_reaction_accent','text_id':None}]
            elif index==0 and outside:selected=[{'category':'wind','reason':'outdoor_summary_accent','text_id':None}]
        for cue in selected[:1]:
            if cue['reason'] in ('dramatic_tension_accent','light_reaction_accent','outdoor_summary_accent'):
                if cue['category'] in stylistic:
                    review.append({'panel_id':panel_id,'reason':'repeated_scene_accent_suppressed'});continue
                stylistic.add(cue['category'])
            if accents>=3:
                review.append({'panel_id':panel_id,'reason':'page_sound_accent_limit'});continue
            accents+=1
            category=cue['category']
            output.append({**cue,'panel_id':panel_id,'t':.12 if category=='impact' else .25,
                           'gain_db':-18 if category in ('wind','rain') else -14 if category=='heartbeat' else -12,
                           'needs_review':True})
    return output,review
