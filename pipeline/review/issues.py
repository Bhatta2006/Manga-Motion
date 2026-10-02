"""Preflight references all unavailable confidence and stage review reasons."""
from pipeline.store import read_json
from pipeline.ingest.hashes import object_hash
from pipeline.review.corrections import load,effective_page,geometry_hash
from pipeline.motion.compiler import camera_record
from pipeline.motion.pacing import pacing_labels

def review(store):
    analysis=read_json(store.asset('analysis.json'))
    if not analysis or not analysis.get('pages'):raise ValueError('Process chapter analysis before reviewing')
    corrections=load(store,analysis);directed=read_json(store.asset('cache/director.json')) or {}
    if directed and directed.get('analysis_sha256')!=object_hash(analysis):raise ValueError('Director is stale; rerun processing')
    tags={p['page_sha256']:p for p in directed.get('pages',[])};labels=pacing_labels(store,analysis);pages=[];issues=[]
    def issue(page,kind,target,bbox,reasons):
        issues.append({'id':object_hash([page['page_sha256'],kind,target,reasons]),'page_sha256':page['page_sha256'],'kind':kind,'target':target,'bbox':bbox,'reasons':reasons})
    for raw in analysis['pages']:
        page=effective_page({**raw,**tags.get(raw['page_sha256'],{})},corrections);fix=corrections['pages'].get(raw['page_sha256'],{})
        effective=camera_record(page,labels.get(raw['page_sha256'],{}));full=[0,0,*page['size']]
        if page['order'].get('needs_review'):issue(page,'order','order',full,page['order'].get('reasons',[]) or ['order_uncertain'])
        for text in effective['texts']:
            patch=fix.get('texts',{}).get(text['id'],{})
            if not patch.get('confirmed'):
                reasons=list(dict.fromkeys(text.get('review_reasons',[])+(['ocr_confidence_unavailable'] if text.get('confidence') is None else [])+(['text_kind_unknown'] if text['kind']=='unknown' else [])))
                if reasons:issue(page,'text',text['id'],text['bbox'],reasons)
            if text['kind'] in ('dialogue','caption') and not patch.get('speaker'):issue(page,'speaker',text['id'],text['bbox'],['speaker_unassigned_voice_stage_pending'])
        semantics=page.get('semantics',{});semantics_by={p['id']:p for p in semantics.get('panels',[])}
        if semantics.get('needs_review'):
            for panel in page['panels']:
                if not fix.get('panels',{}).get(panel['id'],{}).get('confirmed'):issue(page,'scene',panel['id'],panel['bbox'],semantics.get('review_reasons',[]) or ['scene_unverified'])
        for flag in page['review']:
            if flag.get('kind') not in ('confidence','text','order'):issue(page,'geometry',flag.get('id','page'),full,[flag.get('reason','review_required')])
        pages.append({'id':page['id'],'page_sha256':page['page_sha256'],'geometry_sha256':geometry_hash(raw),'size':page['size'],'order':page['order']['panel_ids'],'panels':page['panels'],
                      'texts':[{**t,'speaker':fix.get('texts',{}).get(t['id'],{}).get('speaker')} for t in effective['texts']],
                      'scenes':semantics_by,'notes':page['review']})
    for name,kind in (('camera-audit.json','motion'),('scene-sfx.json','sound'),('music-scenes.json','music')):
        audit=read_json(store.asset('cache/'+name)) or {}
        for entry in audit.get('pages',[]):
            digest=entry.get('page_sha256');page=next((p for p in analysis['pages'] if p['page_sha256']==digest),None)
            if not page:continue
            flags=entry.get('review',[])+[e['audit'] for e in entry.get('events',[]) if e.get('audit',{}).get('needs_review')]
            bounds={p['id']:p['bbox'] for p in page['panels']}
            for flag in flags:
                target=flag.get('panel_id',flag.get('panel',flag.get('id','page')))
                issue(page,kind,target,bounds.get(target,[0,0,*page['size']]),[flag.get('reason',str(flag))])
    return {'corrections':corrections,'revision':object_hash(corrections),'pages':pages,'issues':issues,
            'unresolved':len(issues),'voice_ready':False,'confidence_note':'Model confidence is unavailable; a human confirmation does not calibrate it.'}
