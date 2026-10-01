"""Check actual source hashes, compiler determinism, continuous paths and audits."""
import json
import os
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.build_motion import build_motion
from pipeline.cache import page_sha256
from pipeline.motion.compiler import CameraAdapter
from pipeline.motion.serialize import validate_contract
from pipeline.motion.solver import contains, interpolate
from pipeline.store import write_json


def main():
    root=Path(__file__).resolve().parents[1]
    chapter=root/'library/golden-m1b/chapter'
    before=page_sha256(chapter/'motionscript.json')
    with patch.object(CameraAdapter,'run_page',side_effect=AssertionError('Warm solver recomputed')):
        script,warm=build_motion(root/'library','golden-m1b','chapter',Path(os.environ['MANGAMOTION_RUNTIME']))
    assert before==page_sha256(chapter/'motionscript.json') and warm['stage']['cache_hits']==5
    validate_contract(script)
    analysis=json.loads((chapter/'analysis.json').read_text())
    audit=json.loads((chapter/'cache/camera-audit.json').read_text())
    baseline=json.loads((root/'reports/M0a-cold-metrics.json').read_text())
    samples=0
    for page,record,proof,source in zip(script['pages'],analysis['pages'],audit['pages'],baseline['pages']):
        assert page_sha256(chapter/page['image'])==record['page_sha256']==page_sha256(Path(source['page']))==source['page_sha256']
        assert [p['id'] for p in page['panels']]==[f"{page['id']}_{i}" for i in record['order']['panel_ids']]
        for panel,geometry in zip(page['panels'],proof['panels']):
            camera=panel['timeline'][0]
            for i in range(101):
                frame=interpolate(camera['from'],camera['to'],i/100)
                assert contains(geometry['allowed'],frame) and contains(frame,geometry['protected'])
                samples+=1
    all_panels=[p for page in audit['pages'] for p in page['panels']]
    result={'original_and_served_hashes_unchanged':5,'panels':len(all_panels),'continuous_path_samples':samples,
            'warm_hash_unchanged':True,'max_relative_scale':max(p['max_relative_scale'] for p in all_panels),
            'max_zoom_rate_per_second':max(p['max_zoom_rate_per_second'] for p in all_panels),
            'max_pan_panel_widths_per_second':max(p['max_pan_panel_widths_per_second'] for p in all_panels),
            'central_focus_passes':sum(p['target_central_60_percent'] for p in all_panels),
            'constraint_violations':sum(p['constraint_violations'] for p in all_panels),
            'text_overflow_bleed_panels':sum(p['text_overflow_bleed'] for p in all_panels),
            'transitions':{kind:sum(p['transition_out']['type']==kind for page in script['pages'] for p in page['panels']) for kind in ('cut','glide','fade')},
            'small_text_box_proxy_flags':{str(view):sum(len(r['small_text_boxes']) for p in audit['pages'] for r in p['readability'] if r['viewport']==view) for view in ([390,600],[1280,700])}}
    write_json(root/'reports/M1c-warm.json',warm);write_json(root/'reports/M1c-audit.json',result)
    print(json.dumps({'warm':warm,'audit':result},indent=2))


if __name__=='__main__':main()
