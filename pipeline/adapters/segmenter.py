"""Pinned SAM 2.1 image segmentation; masks select original art, never replace it."""
from pathlib import Path
import os
import sys
import zipfile
import math
from pipeline.cache import JsonStageCache,page_sha256
from pipeline.ingest.hashes import object_hash

SOURCE_REVISION='05d9e57fb3945b10c861046c1e6749e2bfc258e3'
ARCHIVE_SHA256='d33ec1b6678caad324c5a1e3e54285423ca75d104e5fe102c15e884af484094e'
WEIGHT_SHA256='6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38'
REVISION=f'sam2.1-small-{SOURCE_REVISION}-panel-box-v1'

def panel_for(box,panels):
    def overlap(p):
        r=p['bbox'];return max(0,min(r[2],box[2])-max(r[0],box[0]))*max(0,min(r[3],box[3])-max(r[1],box[1]))
    if not panels:return None
    panel=max(panels,key=overlap)
    return panel if overlap(panel)/max(1,(box[2]-box[0])*(box[3]-box[1]))>=.9 else None

def verify_source(root):
    archive=root/'.runtime/vendor'/f'sam2-{SOURCE_REVISION}.zip';folder=archive.with_suffix('')
    if page_sha256(archive)!=ARCHIVE_SHA256:raise ValueError('SAM 2 source archive hash mismatch')
    expected=set()
    with zipfile.ZipFile(archive) as bundle:
        prefix=f'sam2-{SOURCE_REVISION}/'
        for item in bundle.infolist():
            relative=item.filename.removeprefix(prefix)
            if relative.startswith('sam2/') and relative.endswith(('.py','.yaml')):
                expected.add(relative);file=(folder/relative).resolve()
                if not file.is_relative_to(folder.resolve()) or file.read_bytes()!=bundle.read(item):raise ValueError('SAM 2 source differs from pinned archive')
    actual={str(p.relative_to(folder)).replace('\\','/') for p in (folder/'sam2').rglob('*') if p.suffix in ('.py','.yaml')}
    if expected!=actual:raise ValueError('Unexpected SAM 2 source/config file')
    return folder

class Sam2Adapter:
    stage_name='character-segmentation';revision=REVISION;heavy=True
    def __init__(self,store,records):self.store,self.records=store,records;self.predictor=None
    def load(self):
        for key in ('MANGAMOTION_RUNTIME','TEMP','TMP','TORCH_HOME'):
            if Path(os.environ.get(key,'')).drive.upper()!='D:':raise RuntimeError(f'{key} must be on D:')
        import torch
        from importlib.metadata import version
        if version('torch')!='2.4.1+cu121' or version('torchvision')!='0.19.1+cu121':raise RuntimeError('SAM 2 measured runtime pins changed; verify before use')
        if not torch.cuda.is_available():raise RuntimeError('CUDA unavailable')
        root=Path(__file__).resolve().parents[2];folder=verify_source(root);weights=root/'models/sam2/sam2.1_hiera_small.pt'
        if page_sha256(weights)!=WEIGHT_SHA256:raise ValueError('SAM 2 checkpoint hash mismatch')
        sys.path.insert(0,str(folder))
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        if not Path(sys.modules['sam2'].__file__).resolve().is_relative_to(folder):raise ValueError('Unexpected SAM 2 module import')
        # Upstream pinned loader uses unrestricted pickle. Use Torch's existing
        # weights-only loader, strict keys, and verified official bytes instead.
        model=build_sam2('configs/sam2.1/sam2.1_hiera_s.yaml',ckpt_path=None,device='cpu',apply_postprocessing=False)
        model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True)['model'],strict=True)
        model=model.to('cuda').eval();self.predictor=SAM2ImagePredictor(model,max_hole_area=0,max_sprinkle_area=0)
    def unload(self):
        if self.predictor:self.predictor.reset_predictor()
        self.predictor=None
    def run_page(self,path):
        if self.predictor is None:raise RuntimeError('Segmenter not loaded')
        import numpy as np
        import torch
        from PIL import Image
        record=self.records[page_sha256(path)]
        with Image.open(path) as image:rgb=np.array(image.convert('RGB'),copy=True)
        masks=[];review=[]
        grouped={p['id']:[] for p in record['panels']}
        for char in record['characters']:
            panel=panel_for(char['bbox'],record['panels'])
            if panel:grouped[panel['id']].append(char)
            else:review.append({'character':char['id'],'reason':'character_panel_assignment_uncertain'})
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            for panel in record['panels']:
                chars=grouped[panel['id']]
                if not chars:continue
                x,y,r,b=[math.ceil(v) if i<2 else math.floor(v) for i,v in enumerate(panel['bbox'])]
                self.predictor.set_image(rgb[y:b,x:r])
                for char in chars:
                    box=np.array(char['bbox'])-np.array([x,y,x,y])
                    predicted,scores,_=self.predictor.predict(box=box,multimask_output=False)
                    mask=predicted[0].astype(bool);ys,xs=np.nonzero(mask)
                    if not len(xs):review.append({'character':char['id'],'reason':'segmentation_empty'});continue
                    # Include one original-pixel collar; alpha outside the subject
                    # stays zero. This is a mask asset, not replacement art RGB.
                    l=max(0,int(xs.min())-1);t=max(0,int(ys.min())-1);rr=min(r-x,int(xs.max())+2);bb=min(b-y,int(ys.max())+2)
                    alpha=(mask[t:bb,l:rr]*255).astype('uint8');rgba=np.full((*alpha.shape,4),255,dtype='uint8');rgba[:,:,3]=alpha
                    name=f'layers/{record["page_sha256"]}-{panel["id"]}-{char["id"]}-sam.png';asset=self.store.asset(name);asset.parent.mkdir(exist_ok=True)
                    Image.fromarray(rgba,'RGBA').save(asset)
                    masks.append({'id':char['id'],'panel_id':panel['id'],'source_bbox':[x+l,y+t,x+rr,y+bb],'prompt_bbox':char['bbox'],
                                  'mask':name,'mask_sha256':page_sha256(asset),'mask_pixels':int(mask.sum()),'predicted_iou_uncalibrated':float(scores[0])})
                self.predictor.reset_predictor()
        value={'masks':masks,'review':review};return {**value,'content_sha256':object_hash(value)}

class MaskCache(JsonStageCache):
    def __init__(self,root,store):super().__init__(root);self.store=store
    def read(self,stage,key):
        value=super().read(stage,key)
        if not value:return None
        try:
            if value['content_sha256']!=object_hash({k:value[k] for k in ('masks','review')}):return None
            for mask in value['masks']:
                if page_sha256(self.store.asset(mask['mask']))!=mask['mask_sha256']:return None
            return value
        except (KeyError,ValueError,TypeError,OSError):return None
