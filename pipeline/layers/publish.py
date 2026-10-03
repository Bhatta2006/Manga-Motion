"""Bind visually inspected layer candidates to source geometry before publication."""
import argparse
import copy
from pathlib import Path
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.ingest.hashes import object_hash
from pipeline.cache import page_sha256

def geometry(analysis):
    return object_hash([{'id':p['id'],'source':p['page_sha256'],'panels':p['panels'],'texts':[{k:t[k] for k in ('id','bbox','panel_id')} for t in p['texts']]} for p in analysis['pages']])

def enable(store,ids):
    candidates=read_json(store.asset('cache/layer-candidates.json'));analysis=read_json(store.asset('analysis.json'))
    if not candidates or not analysis:raise ValueError('Prepare and visually inspect real layer candidates first')
    entries={item['layer']['id']:item for p in candidates['pages'] for item in p['accepted']}
    if set(ids)-set(entries):raise ValueError('Unknown or rejected layer candidate')
    record={'version':1,'revision':candidates['revision'],'source_geometry_sha256':geometry(analysis),'enabled':{i:object_hash(entries[i]) for i in ids}}
    write_json(store.asset('layer-enabled.json'),record);return record

def attach(script,store,expected=None):
    approved=read_json(store.asset('layer-enabled.json'))
    if expected is not None and object_hash(approved)!=expected:raise ValueError('Enabled layers changed during compilation')
    if not approved:return script
    analysis=read_json(store.asset('analysis.json'));candidate=read_json(store.asset('cache/layer-candidates.json'))
    if not analysis or not candidate or approved.get('version')!=1 or approved.get('revision')!=candidate['revision'] or approved.get('source_geometry_sha256')!=geometry(analysis):raise ValueError('Character layer preparation is stale; re-prepare/review')
    result=copy.deepcopy(script);enabled=approved['enabled'];found=set()
    current={p['id']:p for p in result['pages']}
    for p in candidate['pages']:
        if p['id'] not in current:continue
        page=current[p['id']]
        if page_sha256(store.asset(page['image']))!=p['page_sha256']:raise ValueError('Layer source changed')
        for item in p['accepted']:
            layer=item['layer'];id=layer['id']
            if id not in enabled:continue
            if object_hash(item)!=enabled[id] or page_sha256(store.asset(layer['mask']))!=layer['safety']['mask_sha256']:raise ValueError('Layer candidate changed; re-prepare/review')
            panel=next((q for q in page['panels'] if q['id']==p['id']+'_'+item['panel_id']),None)
            if panel is None:raise ValueError('Enabled layer panel missing')
            panel.setdefault('layers',[]).append(copy.deepcopy(layer));found.add(id)
    known={i['layer']['id'] for p in candidate['pages'] for i in p['accepted']}
    if set(enabled)-known:raise ValueError('Enabled layer candidate missing')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--series',required=True);parser.add_argument('--chapter',required=True);parser.add_argument('--enable',nargs='*',default=[]);args=parser.parse_args()
    store=ChapterStore(Path(__file__).resolve().parents[2]/'library',args.series,args.chapter)
    with store.lock():print(enable(store,args.enable))
if __name__=='__main__':main()
