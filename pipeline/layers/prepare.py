"""Prepare conservative original-pixel layer candidates after segmentation."""
import argparse
import os
import time
from pathlib import Path
import numpy as np
from PIL import Image
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.cache import JsonStageCache,page_sha256
from pipeline.ingest.hashes import object_hash
from pipeline.runtime.scheduler import StageScheduler
from pipeline.layers.segment import segment
from pipeline.layers.masks import prepare_mask,save_candidate,REVISION

class LayerAdapter:
    stage_name='character-layer-proof';revision=REVISION+'-upper-38-v1';heavy=False
    def __init__(self,store,records):self.store,self.records=store,records
    def load(self):pass
    def unload(self):pass
    def run_page(self,path):
        page,entry=self.records[page_sha256(path)]
        with Image.open(path) as image:rgb=np.array(image.convert('RGB'),copy=True)
        panels={p['id']:p for p in page['panels']};accepted=[];rejected=[]
        for raw in entry['masks']:
            with Image.open(self.store.asset(raw['mask'])) as image:mask=np.array(image.getchannel('A'))>0
            panel=panels[raw['panel_id']];texts=[t['bbox'] for t in page['texts']]
            prepared,reason=prepare_mask(rgb,mask,raw['source_bbox'],panel['bbox'],texts,raw['prompt_bbox']);scope='full silhouette'
            if reason and raw['source_bbox'][3]-raw['source_bbox'][1]>250:
                x,y,r,b=raw['source_bbox'];region=[max(panel['bbox'][0],x-20),max(panel['bbox'][1],y-20),min(panel['bbox'][2],r+20),y+int((b-y)*.38)]
                prepared,head_reason=prepare_mask(rgb,mask,raw['source_bbox'],panel['bbox'],texts,raw['prompt_bbox'],region)
                if not head_reason:reason=None;scope='upper character cutout with fixed lower attachment'
                else:reason+=' / upper: '+head_reason
            if reason:rejected.append({'id':raw['id'],'panel_id':panel['id'],'reason':reason})
            else:accepted.append({'panel_id':panel['id'],'scope':scope,'layer':save_candidate(self.store,page,panel,raw,prepared),'audit':prepared['audit']})
        value={'accepted':accepted,'rejected':rejected};return {**value,'content_sha256':object_hash(value)}

class LayerCache(JsonStageCache):
    def __init__(self,root,store):super().__init__(root);self.store=store
    def read(self,stage,key):
        value=super().read(stage,key)
        if not value:return None
        try:
            if value['content_sha256']!=object_hash({k:value[k] for k in ('accepted','rejected')}):return None
            for item in value['accepted']:
                if page_sha256(self.store.asset(item['layer']['mask']))!=item['layer']['safety']['mask_sha256']:return None
            return value
        except (ValueError,KeyError,TypeError,OSError):return None

def prepare(library,series,chapter,runtime):
    started=time.perf_counter();raw,segmentation=segment(library,series,chapter,runtime);store=ChapterStore(library,series,chapter)
    with store.lock():
        analysis=read_json(store.asset('analysis.json'));raw_by={p['page_sha256']:p for p in raw['pages']};records={};inputs={};paths=[]
        for p in analysis['pages']:
            path=store.asset(p['image']);digest=p['page_sha256']
            if page_sha256(path)!=digest:raise ValueError('Source art changed')
            records[digest]=(p,raw_by[digest]);inputs[digest]={'raw_masks':raw_by[digest]['content_sha256'],'geometry':{k:p[k] for k in ('id','panels','texts')}};paths.append(path)
        results,proof=StageScheduler(runtime,LayerCache(store.asset('cache/stages'),store)).run_pages(LayerAdapter(store,records),paths,page_configs=inputs)
        candidate={'revision':LayerAdapter.revision,'geometry_sha256':object_hash(inputs),'pages':[{'id':p['id'],**v} for p,v in zip(analysis['pages'],results)],'status':'unpublished; visual review required'}
        write_json(store.asset('cache/layer-candidates.json'),candidate)
        return candidate,{'segmentation':segmentation,'proof':proof,'elapsed_seconds':round(time.perf_counter()-started,4)}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--series',required=True);parser.add_argument('--chapter',required=True);parser.add_argument('--report',required=True,type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];report=args.report.resolve()
    if report.drive.upper()!='D:':raise ValueError('Report must be on D:')
    result,metrics=prepare(root/'library',args.series,args.chapter,Path(os.environ['MANGAMOTION_RUNTIME']));write_json(report,metrics)
    print({'pages':len(result['pages']),'candidates':sum(len(p['accepted']) for p in result['pages']),'rejected':sum(len(p['rejected']) for p in result['pages']),'report':str(report)})
if __name__=='__main__':main()
