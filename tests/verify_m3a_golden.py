import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.director.chapter import direct_chapter
from pipeline.adapters.director_local import LocalQwenDirector
from pipeline.build_motion import build_motion
from pipeline.director.validate import validate_output
from pipeline.motion.serialize import validate_contract
from pipeline.cache import page_sha256
from pipeline.store import read_json,write_json
root=Path(__file__).resolve().parents[1];chapter=root/'library/golden-m1d/chapter'
analysis=read_json(chapter/'analysis.json');reference=read_json(root/'library/golden-m1b/reference.json')
with patch.object(LocalQwenDirector,'load',side_effect=AssertionError('Warm model loaded')):
    output,metrics=direct_chapter(root/'library','golden-m1d','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
assert metrics['stage']['cache_hits']==5
hits=total=0;categories={};beats={}
for page,directed,labels in zip(analysis['pages'],output['pages'],reference['pages']):
    semantics=directed['semantics'];assert semantics['provider']=='local-qwen3-vl'
    validate_output({k:semantics[k] for k in ('summary','panels')},{**page,'characters':directed['characters']})
    kinds={t['id']:t['kind'] for p in semantics['panels'] for t in p['texts']}
    assigned={t['id'] for t in page['texts'] if t['panel_id'] is not None}
    for label in labels['ocr']:
        key=f'text_{label["text_index"]:03}'
        if key in assigned:
            total+=1;hits+=kinds[key]==label['category']
    for kind in kinds.values():categories[kind]=categories.get(kind,0)+1
    for panel in semantics['panels']:beats[panel['beat']]=beats.get(panel['beat'],0)+1
    assert page_sha256(chapter/page['image'])==page['page_sha256']
script,camera=build_motion(root/'library','golden-m1d','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
validate_contract(script)
result={'warm_metrics':metrics,'camera_metrics':camera,'class_match_provisional':{'correct':hits,'total':total},
        'categories':categories,'beats':beats,'source_hashes_unchanged':True,'all_pages_flagged_unverified':True}
write_json(root/'reports/M3a-golden.json',result)
print(json.dumps(result,indent=2))
