"""Real five-page job through the running loopback API, cold and warm."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default='http://127.0.0.1:5174')
    parser.add_argument('--series',default='golden-m1d')
    args=parser.parse_args()
    latencies=[]
    def call(path,body=None):
        started=time.perf_counter()
        request=Request(args.base+path,data=None if body is None else json.dumps(body).encode(),
                        headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=10) as response:result=json.load(response)
        latencies.append({'route':path.split('?')[0],'ms':(time.perf_counter()-started)*1000})
        return result
    source=PROJECT/'library/fixtures/m1a/folder'
    originals={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.jpg')}
    assert len(originals)==5
    results={}
    for label in ('cold','warm'):
        started=time.perf_counter()
        job=call('/api/imports',{'source':str(source),'series':args.series,'chapter':'chapter','direction':'rtl'})
        print(label,'queued',job['id'],flush=True)
        phases=[];deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            current=call('/api/jobs/'+job['id'])
            phase=(current['phase'],current['progress'].get('completed'),current['progress'].get('state'))
            if not phases or phases[-1]!=phase:
                phases.append(phase);print(label,phase,flush=True)
            if current['status'] in {'completed','failed'}:break
            assert call('/api/health')['status']=='ok'
            call('/api/library')
            time.sleep(.4)
        assert current['status']=='completed',current.get('error')
        elapsed=time.perf_counter()-started
        info=call(f'/api/chapters/{args.series}/chapter/playback')
        script=call(info['script_url'])
        assert info['pages']==5 and info['panels']==25
        assert script['version']==1 and script['direction']=='rtl'
        assert [p['id'] for p in script['pages']]==[f'p{i:04d}' for i in range(1,6)]
        for page in script['pages']:
            with urlopen(args.base+info['asset_base']+page['image']) as response:data=response.read()
            assert hashlib.sha256(data).hexdigest()==Path(page['image']).stem
        results[label]={'job':current,'request_to_readable_seconds':round(elapsed,6),'phases':phases}
        metrics=current['metrics']
        if label=='cold':assert all(s['cache_hits']==0 for s in metrics['analysis']['stages'])
        else:
            assert all(s['cache_hits']==5 and s['load_seconds']==0 for s in metrics['analysis']['stages'])
            assert metrics['camera']['stage']['cache_hits']==5
        print(label,'completed',round(elapsed,3),'seconds',flush=True)
    assert originals=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.jpg')}
    results['api_latency_samples']=latencies
    results['input_hashes_unchanged']=5
    (PROJECT/'reports/M1d-golden.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print('PASS: five pages / 25 panels, cold/warm, immutable pixels and responsive API',flush=True)


if __name__=='__main__':main()
