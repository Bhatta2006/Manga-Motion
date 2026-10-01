"""Small deterministic motion study. These are not VLM semantic judgments."""
import math
import numpy as np
from PIL import Image
from pipeline.cache import page_sha256
from pipeline.layers.integrity import eligible_region


def overlap(a, b):
    return max(0, min(a[2],b[2])-max(a[0],b[0]))*max(0, min(a[3],b[3])-max(a[1],b[1]))


def assign_panel(box, panels):
    areas = [overlap(box, p) for p in panels]
    if max(areas) > 0:
        return areas.index(max(areas))
    cx,cy = (box[0]+box[2])/2,(box[1]+box[3])/2
    return min(range(len(panels)), key=lambda i: ((panels[i][0]+panels[i][2])/2-cx)**2+((panels[i][1]+panels[i][3])/2-cy)**2)


def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]


def frames(panel, bubbles, size, index):
    """Expand framing first, then end at protected bounds. Never crop text."""
    protected = union([panel]+bubbles)
    protected = [max(0,protected[0]-8),max(0,protected[1]-8),min(size[0],protected[2]+8),min(size[1],protected[3]+8)]
    w,h = protected[2]-protected[0],protected[3]-protected[1]
    margin = .04 if index % 3 != 2 else .02
    broad = [max(0,protected[0]-w*margin),max(0,protected[1]-h*margin),min(size[0],protected[2]+w*margin),min(size[1],protected[3]+h*margin)]
    if index % 3 == 0:
        return broad, protected, "push_in"
    if index % 3 == 1:
        return protected, broad, "pull_out"
    # Horizontal drift across spare margin; both endpoints contain protection.
    return [broad[0], broad[1], protected[2], broad[3]], [protected[0], broad[1], broad[2], broad[3]], "pan"


class FixedMotionAdapter:
    stage_name = "fixed-motion"
    revision = "visual-m0b-1"
    heavy = False

    def __init__(self, records):
        self.records = records
    def load(self): pass
    def unload(self): pass

    def run_page(self, page):
        record = self.records[page_sha256(page)]
        det, size = record['detections'], record['size']
        boxes = [[round(x,3) for x in b] for b in det['panels']]
        text_groups = [[] for _ in boxes]
        for i,b in enumerate(det['texts']):
            text_groups[assign_panel(b,boxes)].append((i,b))
        with Image.open(page) as im:
            rgb = np.array(im.convert('RGB'))
        panels, layer_audit = [], []
        for i,box in enumerate(boxes):
            texts = text_groups[i]
            start,end,move = frames(box,[b for _,b in texts],size,i)
            # Reading dwell uses OCR length only; no spoken lines or invented speech.
            words = sum(len(record['ocr'][j]['text'].split()) for j,_ in texts)
            duration = round(min(12,max(2.5,1.5+words/3.0)),3)
            focus = [{'kind':'bubble','ref':f'b{j}','bbox':b} for j,b in texts]
            for ci,char in enumerate(det['characters']):
                if assign_panel(char,boxes) != i: continue
                region,reason = eligible_region(rgb,char,box,[b for _,b in texts])
                layer_audit.append({'panel_index':i,'character_index':ci,'region':region,'rejection':reason})
                if region is not None:
                    focus.append({'kind':'region','ref':'parallax-safe','bbox':region})
                    break  # One bounded plane per panel in this small prototype.
            panels.append({'bbox':box,'director':{'beat':'quiet' if not texts else 'dialogue','shot':'wide','energy':0.15,'mood':[],'time_skip':False,'focus':focus},
                'timeline':[{'t':0,'type':'camera','move':move,'from':start,'to':end,'dur':duration,'ease':'inOutSine'}],
                'transition_out':{'type':'glide','dur':.32},'confidence':{'panel':None,'ocr':None,'speaker':None}})
        return {'size':size,'panels':panels,'layer_audit':layer_audit}
