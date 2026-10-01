"""Strict semantic IDs/enums; model output cannot introduce pixel coordinates."""
import math

BEATS=('establish','dialogue','reaction','reveal','impact','chase','comedy','flashback','quiet','transition')
SHOTS=('wide','medium','closeup','extreme_closeup','splash','insert')
KINDS=('dialogue','caption','sfx','watermark','translator_note','sign','nonverbal','unknown')
DELIVERIES=('speak','shout','whisper','think','narrate','cry','laugh')
SFX=('impact','whoosh','footsteps','door','heartbeat','rain','wind','chime','none')


def output_schema(record):
    def obj(properties):return {'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}
    def enum(values):return {'type':'string','enum':list(values)}
    number={'type':'number','minimum':0,'maximum':1}
    texts=[t['id'] for t in record['texts']]
    # Empty arrays are constrained separately to avoid invalid empty enums.
    text_item=obj({'kind':enum(KINDS),'delivery':enum(DELIVERIES),'intensity':number})
    panels={}
    for source in record['panels']:
        assigned=[t['id'] for t in record['texts'] if t['panel_id']==source['id']]
        refs=assigned+[c['id'] for c in record.get('characters',[])]+[source['id']]
        focus_item=obj({'kind':enum(('face','object','bubble','region')),'ref':enum(refs)})
        panels[source['id']]=obj({'beat':enum(BEATS),'shot':enum(SHOTS),
                   'energy':number,'mood':{'type':'array','maxItems':3,'items':{'type':'string','maxLength':24}},
                   'time_skip':{'type':'boolean'},'focus':{'type':'array','maxItems':3,'items':focus_item},
                   'texts':obj({text_id:text_item for text_id in assigned}),
                   'sfx':{'type':'array','maxItems':2,'items':obj({'category':enum(SFX),'text_id':enum(assigned+['scene'])})}})
    return obj({'summary':{'type':'string','maxLength':400},'panels':obj(panels)})


def decode_output(value,record):
    exact_keys(value,('summary','panels'))
    exact_keys(value['panels'],[p['id'] for p in record['panels']])
    panels=[]
    for panel in record['panels']:
        tags=value['panels'][panel['id']]
        exact_keys(tags,('beat','shot','energy','mood','time_skip','focus','texts','sfx'))
        exact_keys(tags['texts'],[t['id'] for t in record['texts'] if t['panel_id']==panel['id']])
        panels.append({**tags,'id':panel['id'],'texts':[{'id':key,**data} for key,data in tags['texts'].items()]})
    return validate_output({'summary':value['summary'],'panels':panels},record)


def exact_keys(value,expected):
    if not isinstance(value,dict) or set(value)!=set(expected):raise ValueError('Unexpected semantic fields')


def unit(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid semantic intensity')


def validate_output(value,record):
    exact_keys(value,('summary','panels'))
    if not isinstance(value['summary'],str) or len(value['summary'])>400:raise ValueError('Invalid scene summary')
    panels={p['id'] for p in record['panels']};texts={t['id']:t for t in record['texts']}
    characters={c['id'] for c in record.get('characters',[])}
    if not isinstance(value['panels'],list) or len(value['panels'])!=len(panels):raise ValueError('Missing semantic panels')
    seen=set();seen_text=set()
    for panel in value['panels']:
        exact_keys(panel,('id','beat','shot','energy','mood','time_skip','focus','texts','sfx'))
        if panel['id'] not in panels or panel['id'] in seen:raise ValueError('Unknown/duplicate semantic panel')
        seen.add(panel['id']);unit(panel['energy'])
        if panel['beat'] not in BEATS or panel['shot'] not in SHOTS or type(panel['time_skip']) is not bool:raise ValueError('Invalid semantic enum')
        if not isinstance(panel['mood'],list) or len(panel['mood'])>3 or any(not isinstance(x,str) or len(x)>24 for x in panel['mood']):raise ValueError('Invalid mood')
        if not isinstance(panel['focus'],list) or len(panel['focus'])>3:raise ValueError('Invalid focus list')
        for focus in panel['focus']:
            exact_keys(focus,('kind','ref'))
            if focus['kind'] not in ('face','object','bubble','region'):raise ValueError('Unknown focus kind')
            if focus['ref'] not in panels|set(texts)|characters:raise ValueError('Unknown focus reference')
            if focus['ref'] in texts and texts[focus['ref']]['panel_id']!=panel['id']:raise ValueError('Focus text belongs to another panel')
        if not isinstance(panel['texts'],list):raise ValueError('Invalid semantic text list')
        for text in panel['texts']:
            exact_keys(text,('id','kind','delivery','intensity'))
            if text['id'] not in texts or text['id'] in seen_text or texts[text['id']]['panel_id']!=panel['id']:raise ValueError('Unknown/duplicate text association')
            seen_text.add(text['id']);unit(text['intensity'])
            if text['kind'] not in KINDS or text['delivery'] not in DELIVERIES:raise ValueError('Unknown text kind/delivery')
        if not isinstance(panel['sfx'],list) or len(panel['sfx'])>2:raise ValueError('Invalid SFX list')
        for cue in panel['sfx']:
            exact_keys(cue,('category','text_id'))
            if cue['category'] not in SFX or (cue['text_id']!='scene' and cue['text_id'] not in {t['id'] for t in panel['texts']}):raise ValueError('Unknown SFX category/text')
    if seen_text!={t['id'] for t in record['texts'] if t['panel_id'] is not None}:raise ValueError('Missing text classifications')
    return value
