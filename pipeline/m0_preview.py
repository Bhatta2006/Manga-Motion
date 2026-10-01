"""Build only the approved five-page visual/SFX preview from measured M0a caches."""
import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from PIL import Image
from pipeline.cache import JsonStageCache, page_sha256
from pipeline.runtime.scheduler import StageScheduler, DeviceMemorySampler
from pipeline.motion.fixed import FixedMotionAdapter, assign_panel
from pipeline.motion.serialize import validate_geometry
from pipeline.adapters.sfx import ProceduralSfxAdapter, materialize


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-label',default='cold',choices=['cold','warm','repair'])
    args=parser.parse_args()
    project=Path(__file__).resolve().parents[1]
    runtime=Path(os.environ.get('MANGAMOTION_RUNTIME',''))
    if not runtime.is_dir() or runtime.drive.upper()!='D:': parser.error('Dot-source scripts/enter-runtime.ps1 first')
    started=time.perf_counter()
    root=project/'library/preview/m0b';root.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((project/'reports/M0a-cold-metrics.json').read_text())
    pages=[Path(x['page']) for x in baseline['pages']]
    records,inputs,cues={}, {}, {}
    sampler=DeviceMemorySampler();sampler.start()
    assets={};clip_metrics=[]
    try:
        for kind in ('wind','turn','chime'):
            clip_started=time.perf_counter();assets[kind]=materialize(root,kind)
            clip_metrics.append({'kind':kind,'run_seconds':round(time.perf_counter()-clip_started,6),'audio_seconds':assets[kind]['duration']})
    finally:
        sampler.stop()
    asset_metrics={'stage':'procedural-library','recipe':'procedural-sfx-1','clips':clip_metrics,
        'device_vram_baseline_mib':sampler.baseline_mib,'device_vram_peak_mib':sampler.peak_mib,
        'process_ram_baseline_mib':sampler.process_ram_baseline_mib,'process_ram_peak_mib':sampler.process_ram_peak_mib,
        'note':'Generates deterministic PCM and repairs missing/corrupted WAVs even on a warm page cache'}
    for i,page in enumerate(pages,1):
        digest=page_sha256(page)
        if digest!=baseline['pages'][i-1]['page_sha256']: raise ValueError('Source changed since measured M0a')
        cache=project/'library/golden-opt-final/cache'/f'p{i:03d}-{digest[:12]}'
        det=json.loads((cache/'detections.json').read_text())
        ocr=json.loads((cache/'ocr.json').read_text())
        if det['page_sha256']!=digest or ocr['page_sha256']!=digest: raise ValueError('Cache/source mismatch')
        # Clamp detector roundoff to source dimensions; no image modification.
        size=ocr['image_size']
        normalized=det['detections']
        for kind in ('panels','texts','characters'):
            normalized[kind]=[[max(0,min(size[j%2],x)) for j,x in enumerate(b)] for b in normalized[kind]]
        records[digest]={'detections':normalized,'ocr':ocr['ocr'],'size':size}
        inputs[digest]={'input_sha256':fingerprint(records[digest])}
        # Sparse page-turn accent plus two visually reviewed printed wind cues.
        cues[digest]=[(0,0,'turn',-16)] if i>1 else []
        if i==1:
            for ti in (9,11):
                cues[digest].append((assign_panel(normalized['texts'][ti],normalized['panels']),.65,'wind',-10))
    scheduler=StageScheduler(runtime,JsonStageCache(root/'cache/stage'))
    motion,mm=scheduler.run_pages(FixedMotionAdapter(records),pages,page_configs=inputs)
    sfx,sm=scheduler.run_pages(ProceduralSfxAdapter(cues,assets),pages,
        config={'assets':fingerprint(assets)},page_configs={k:{'cues':v} for k,v in cues.items()})
    script={'version':1,'chapter':'preview/m0b','direction':'rtl','characters':{'narrator':{'voice':'unassigned'}},'pages':[]}
    pixels=[];audits=[];first_page=None
    for i,(page,motion_page,sound_page) in enumerate(zip(pages,motion,sfx),1):
        image=f'pages/{i:03d}{page.suffix.lower()}'
        target=root/image;target.parent.mkdir(exist_ok=True)
        if not target.exists() or page_sha256(target)!=page_sha256(page): shutil.copyfile(page,target)
        with Image.open(page) as source,Image.open(target) as served:
            before=source.convert('RGB').tobytes();after=served.convert('RGB').tobytes()
            if before!=after: raise ValueError('Served art pixels differ')
            pixels.append({'page':i,'source_sha256':page_sha256(page),'served_sha256':page_sha256(target),'decoded_rgb_sha256':hashlib.sha256(before).hexdigest(),'pixels_equal':True})
        for j,panel in enumerate(motion_page['panels']):
            panel['id']=f'p{i:03d}_{j+1:02d}'
            panel['timeline'] += [{k:v for k,v in cue.items() if k!='panel_index'} for cue in sound_page['cues'] if cue['panel_index']==j]
            panel['timeline'].sort(key=lambda e:e['t'])
        script['pages'].append({'id':f'p{i:03d}','image':image,'size':motion_page['size'],'panels':motion_page['panels']})
        audits.append({'page':i,'candidates':motion_page['layer_audit']})
        if first_page is None: first_page=time.perf_counter()-started
    validate_geometry(script)
    # Atomic contract publication; readers never see partially written JSON.
    temp=root/'motionscript.tmp';temp.write_text(json.dumps(script,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf8');temp.replace(root/'motionscript.json')
    (root/'cache/layers.json').write_text(json.dumps(audits,indent=2)+'\n',encoding='utf8')
    (root/'sfx/manifest.json').write_text(json.dumps(assets,indent=2)+'\n',encoding='utf8')
    report={'scope':'visual-first M0b; no voice model','motion':mm,'sfx':sm,'asset_generation':asset_metrics,'pixels':pixels,'layers':audits,
        'elapsed_seconds':round(time.perf_counter()-started,4),'first_exported_page_seconds':round(first_page,4),
        'note':'Batch build; first_exported_page is not streaming import latency','panels':sum(len(p['panels']) for p in script['pages']),
        'parallax_accepted':sum(c['region'] is not None for p in audits for c in p['candidates'])}
    (project/f'reports/M0b-{args.run_label}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
