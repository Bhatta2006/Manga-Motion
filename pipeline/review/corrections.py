"""Validated human overlays applied after cached model output, before compilation."""
import copy,json,subprocess
from pathlib import Path
from pipeline.store import read_json,write_json
from pipeline.ingest.hashes import object_hash
from pipeline.vision.text import normalize_text
from pipeline.director.validate import validate_output

PROJECT=Path(__file__).resolve().parents[2]
AUDITS=('cache/camera-audit.json','cache/scene-sfx.json','cache/music-scenes.json')
def empty(store,analysis):return {'version':1,'chapter':f'{store.series}/{store.chapter}','input_sha256':analysis['input_sha256'],'pages':{}}
def geometry_hash(page):
    return object_hash({'size':page['size'],'panels':sorted([(p['id'],p['bbox']) for p in page['panels']]),
                        'texts':sorted([(t['id'],t['bbox'],t['panel_id']) for t in page['texts']])})

def validate(value,store,analysis):
    result=subprocess.run(['node',str(PROJECT/'reader/tools/validate-corrections.mjs')],input=json.dumps(value,ensure_ascii=False,allow_nan=False),
                          text=True,encoding='utf-8',capture_output=True,timeout=20,cwd=PROJECT)
    if result.returncode:raise ValueError('Invalid corrections: '+result.stderr[:2000])
    if value['chapter']!=f'{store.series}/{store.chapter}' or value['input_sha256']!=analysis['input_sha256']:raise ValueError('Corrections belong to another chapter/import')
    pages={p['page_sha256']:p for p in analysis['pages']}
    for digest,fix in value['pages'].items():
        if digest not in pages:raise ValueError('Unknown correction page')
        page=pages[digest];panels={p['id']:p for p in page['panels']};texts={t['id']:t for t in page['texts']}
        if fix['geometry_sha256']!=geometry_hash(page):raise ValueError('Detection geometry changed; review/rebind corrections before applying them')
        if 'order' in fix and (len(fix['order'])!=len(panels) or set(fix['order'])!=set(panels)):raise ValueError('Order must be a complete panel permutation')
        if set(fix.get('texts',{}))-set(texts) or set(fix.get('panels',{}))-set(panels):raise ValueError('Unknown correction target')
        for key,patch in fix.get('texts',{}).items():
            target=patch.get('panel_id',texts[key]['panel_id'])
            if target is not None and 'panel_id' in patch and target!=texts[key]['panel_id']:
                if target not in panels:raise ValueError('Unknown text panel')
                box=texts[key]['bbox'];bound=panels[target]['bbox']
                if box[0]<bound[0] or box[1]<bound[1] or box[2]>bound[2] or box[3]>bound[3]:raise ValueError('Selected panel does not contain this text; leave it unassigned for geometry review')
            if patch.get('confirmed') and patch.get('kind',texts[key]['kind'])=='unknown':raise ValueError('Choose a text kind before confirming')
    return value

def recover(store):
    journal=read_json(store.asset('cache/review-transaction.json'))
    if not journal or journal.get('state')!='pending':return
    # A process death during two-file publication restores the last usable pair.
    for name,key in (('corrections.json','previous_corrections'),('motionscript.json','previous_script')):
        value=journal[key]
        if value is None:store.asset(name).unlink(missing_ok=True)
        else:write_json(store.asset(name),value)
    for name in AUDITS:
        if name not in journal.get('previous_audits',{}):continue
        value=journal['previous_audits'][name]
        if value is None:store.asset(name).unlink(missing_ok=True)
        else:write_json(store.asset(name),value)
    journal['state']='rolled_back';write_json(store.asset('cache/review-transaction.json'),journal)

def load(store,analysis):
    path=store.asset('corrections.json');value=read_json(path)
    if path.exists() and value is None:raise ValueError('Corrections file is damaged')
    return validate(value,store,analysis) if value is not None else empty(store,analysis)

def effective_page(page,corrections):
    result=copy.deepcopy(page);fix=corrections.get('pages',{}).get(page['page_sha256'],{})
    if not fix:return result
    if 'order' in fix:result['order']['panel_ids']=fix['order'][:]
    if fix.get('order_confirmed'):result['order'].update(needs_review=False,reasons=[])
    for text in result['texts']:
        patch=fix.get('texts',{}).get(text['id'],{})
        for key in ('text','kind','panel_id','speaker'):
            if key in patch:text[key]=normalize_text(patch[key]) if key=='text' else patch[key]
        if 'kind' in patch:text['human_kind']=patch['kind']
        if patch.get('confirmed'):text.update(needs_review=False,review_reasons=[],human_confirmed=True)
    semantics=result.get('semantics')
    if semantics:
        original={t['id']:copy.deepcopy(t) for panel in semantics['panels'] for t in panel['texts']}
        for panel in semantics['panels']:
            patch=fix.get('panels',{}).get(panel['id'],{})
            for key in ('beat','mood','energy','time_skip'):
                if key in patch:panel[key]=copy.deepcopy(patch[key])
            panel['texts']=[{**original.get(t['id'],{'id':t['id'],'kind':t['kind'],'delivery':'speak','intensity':.5}),
                             **({'kind':fix['texts'][t['id']]['kind']} if 'kind' in fix.get('texts',{}).get(t['id'],{}) else {})}
                            for t in result['texts'] if t['panel_id']==panel['id']]
            assigned={t['id'] for t in panel['texts']}
            panel['sfx']=[s for s in panel['sfx'] if s['text_id']=='scene' or s['text_id'] in assigned]
            panel['focus']=[f for f in panel['focus'] if not f['ref'].startswith('text_') or f['ref'] in assigned]
        if all(fix.get('panels',{}).get(p['id'],{}).get('confirmed') for p in semantics['panels']):
            semantics.update(needs_review=False,review_reasons=[])
        semantics['semantic_sha256']=object_hash({k:semantics[k] for k in ('summary','panels')})
        validate_output({k:semantics[k] for k in ('summary','panels')},result)
    # Remove resolved per-item flags; absence of calibrated scores remains explicit.
    result['review']=[r for r in result['review'] if not (r.get('kind')=='text' and fix.get('texts',{}).get(r.get('id'),{}).get('confirmed'))]
    if fix.get('order_confirmed'):result['review']=[r for r in result['review'] if r.get('kind')!='order']
    return result
