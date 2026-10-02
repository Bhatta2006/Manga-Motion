"""Prepare source-bound raw character masks, without publishing unproven depth."""
import argparse
import os
from pathlib import Path
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.cache import page_sha256
from pipeline.ingest.hashes import object_hash
from pipeline.adapters.segmenter import Sam2Adapter,MaskCache
from pipeline.runtime.scheduler import StageScheduler

def segment(library,series,chapter,runtime):
    store=ChapterStore(library,series,chapter)
    with store.lock():
        analysis=read_json(store.asset('analysis.json'));detected=read_json(store.asset('cache/detections.json'))
        if not analysis or not detected:raise ValueError('Analyzed real pages and detector boxes required')
        geometry={p['page_sha256']:p for p in detected['pages']};records={};paths=[];inputs={}
        for p in analysis['pages']:
            path=store.asset(p['image'])
            if page_sha256(path)!=p['page_sha256']:raise ValueError('Source art changed')
            g=geometry[p['page_sha256']];boxes=g.get('detections',{}).get('characters',[]);ids=g.get('source_indices',{}).get('characters',range(len(boxes)))
            if len(ids)!=len(boxes):raise ValueError('Detector character IDs do not match geometry')
            record={**p,'characters':[{'id':f'char_{i:03}','bbox':box} for i,box in zip(ids,boxes)]};records[p['page_sha256']]=record;paths.append(path)
            inputs[p['page_sha256']]={'panels':record['panels'],'characters':record['characters']}
        outputs,metrics=StageScheduler(runtime,MaskCache(store.asset('cache/stages'),store)).run_pages(Sam2Adapter(store,records),paths,page_configs=inputs)
        result={'revision':Sam2Adapter.revision,'geometry_sha256':object_hash(inputs),'pages':[{'id':p['id'],**v} for p,v in zip(analysis['pages'],outputs)],
                'status':'raw masks only; continuous coverage and visual audit required before publication'}
        write_json(store.asset('cache/character-masks.json'),result);return result,metrics

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--series',required=True);parser.add_argument('--chapter',required=True);parser.add_argument('--report',required=True,type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];runtime=Path(os.environ['MANGAMOTION_RUNTIME']);report=args.report.resolve()
    if report.drive.upper()!='D:':raise ValueError('Report must be on D:')
    result,metrics=segment(root/'library',args.series,args.chapter,runtime);write_json(report,metrics)
    print({'pages':len(result['pages']),'masks':sum(len(p['masks']) for p in result['pages']),'metrics':str(report)})
if __name__=='__main__':main()
