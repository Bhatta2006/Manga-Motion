"""Prepare anonymous, time/audio-matched v1 static/fixed/directed comparisons."""
import argparse,copy,json,random,secrets
from pathlib import Path
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.api.chapters import snapshot
from pipeline.motion.rules import panel_rule
from pipeline.motion.solver import solve_camera
from pipeline.motion.serialize import validate_contract
from pipeline.ingest.hashes import object_hash


def prepare(library,series,chapter):
    store=ChapterStore(library,series,chapter)
    with store.lock():
        source=read_json(store.asset('motionscript.json'))
        if not source:raise ValueError('Process this chapter before comparison')
        validate_contract(source);conditions={}
        for kind in ('static','fixed','directed'):
            script=copy.deepcopy(source)
            for page in script['pages']:
                for index,panel in enumerate(page['panels']):
                    if kind=='directed':continue
                    cameras=[e for e in panel['timeline'] if e['type']=='camera'];end=max(e['t']+e['dur'] for e in cameras)
                    if kind=='static':
                        full=[0,0,*page['size']];motion=[{'type':'camera','t':0,'move':'hold','from':full,'to':full,'dur':end,'ease':'linear'}]
                    else:
                        move,_=panel_rule(index,any(f['kind']=='bubble' for f in panel['director']['focus']),len(page['panels'])==1)
                        event,_=solve_camera(panel['bbox'],[f['bbox'] for f in panel['director']['focus'] if f['kind']=='bubble'],page['size'],recipe=move,duration=min(2,end))
                        motion=[event]
                        if end>event['dur']:motion.append({'type':'camera','t':event['dur'],'move':'hold','from':event['to'],'to':event['to'],'dur':end-event['dur'],'ease':'linear'})
                    panel['timeline']=sorted(motion+[e for e in panel['timeline'] if e['type']!='camera'],key=lambda e:e['t'])
                    panel['director'].update(beat='quiet',energy=.1,mood=[],time_skip=False)
                    panel['transition_out']={'type':'fade' if panel['transition_out']['dur'] else 'cut','dur':panel['transition_out']['dur']}
            digest,_=snapshot(store,script);conditions[kind]=digest
        order=list(conditions);random.SystemRandom().shuffle(order)
        trial=secrets.token_hex(8)
        private={'trial':trial,'source_sha256':object_hash(source),'conditions':{chr(65+i):{'condition':kind,'snapshot':conditions[kind]} for i,kind in enumerate(order)}}
        write_json(store.asset(f'cache/evaluation-{trial}.json'),private)
        return {'trial':trial,'samples':[{'label':label,'url':f'/?series={series}&chapter={chapter}&snapshot={entry["snapshot"]}&comparison=1'} for label,entry in private['conditions'].items()]}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--series',required=True);parser.add_argument('--chapter',required=True)
    args=parser.parse_args();print(json.dumps(prepare(Path(__file__).resolve().parents[2]/'library',args.series,args.chapter),indent=2))
