"""Prepare verified local music assets/audit without replacing published playback."""
import argparse,json,os,time
from pathlib import Path
from pipeline.store import ChapterStore,read_json,write_json
from pipeline.ingest.hashes import object_hash
from pipeline.cache import page_sha256
from pipeline.audio.music import prepare_pages,attach
from pipeline.motion.compiler import camera_record
from pipeline.motion.serialize import validate_contract
from pipeline.audio.music_library import REVISION,PROFILES,AMBIENCE,RATE

def prepare_chapter(library,series,chapter,runtime):
    store=ChapterStore(library,series,chapter)
    with store.lock():
        started=time.perf_counter()
        analysis=read_json(store.asset('analysis.json'));directed=read_json(store.asset('cache/director.json'))
        original=read_json(store.asset('motionscript.json'))
        if not analysis or not directed or not original:raise ValueError('Process the chapter with the director before preparing music')
        if directed.get('analysis_sha256')!=object_hash(analysis):raise ValueError('Director is stale for this analysis')
        by_hash={p['page_sha256']:p for p in directed['pages']};records=[];paths=[]
        for page in analysis['pages']:
            if page['page_sha256'] not in by_hash:raise ValueError('Missing director page')
            asset=store.asset(page['image'])
            if page_sha256(asset)!=page['page_sha256']:raise ValueError('Original page changed')
            records.append({'id':page['id'],**camera_record({**page,**by_hash[page['page_sha256']]})});paths.append(asset)
        outputs,stage=prepare_pages(store,records,paths,runtime)
        prepared=attach(original,outputs);validated=validate_contract(prepared)
        if read_json(store.asset('motionscript.json'))!=original:raise ValueError('Published playback changed during preparation')
        for page,path in zip(analysis['pages'],paths):
            if page_sha256(path)!=page['page_sha256']:raise ValueError('Original page changed during preparation')
        audit={'revision':stage['revision'],'pages':outputs,'analysis_sha256':object_hash(analysis),'director_sha256':object_hash(directed)}
        write_json(store.asset('cache/music-scenes.json'),audit)
        write_json(store.asset('cache/prepared-music.json'),prepared)
        write_json(store.checked(store.root/'music/manifest.json'),{'recipe':REVISION,'profiles':sorted(PROFILES),'ambience':sorted(AMBIENCE),'sample_rate':RATE,
                   'source':'MangaMotion owned procedural tones/noise','license':'Project-generated; personal use authorized','assets_location':'Chapter music/ambience; exact provenance in cache/music-scenes.json'})
        return prepared,{'stage':stage,'validation':validated,'elapsed_seconds':round(time.perf_counter()-started,6),
                         'scenes':len(prepared['scenes']),'beds':sum(len(s['beds']) for s in prepared['scenes'].values()),'published_playback_unchanged':True}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--series',required=True);p.add_argument('--chapter',required=True)
    args=p.parse_args();_,metrics=prepare_chapter(Path(__file__).resolve().parents[2]/'library',args.series,args.chapter,Path(os.environ['MANGAMOTION_RUNTIME']))
    print(json.dumps(metrics,indent=2))
