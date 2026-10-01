"""Monitor device VRAM while the actual local browser acceptance script runs."""
import json
import subprocess
from pathlib import Path
from pipeline.runtime.scheduler import DeviceMemorySampler

project=Path(__file__).resolve().parents[1]
sampler=DeviceMemorySampler(interval_seconds=.2)
sampler.start()
try:
    result=subprocess.run(['node','reader/tests/browser-smoke.mjs'],cwd=project,check=False)
finally:
    sampler.stop()
record={'browser_test_exit_code':result.returncode,'device_vram_baseline_mib':sampler.baseline_mib,'device_vram_peak_mib':sampler.peak_mib,'note':'Global NVIDIA device memory, sampled at 0.2s; excludes integrated GPU. Parent Python process RAM is not reader RAM and is not reported as such.'}
(project/'reports/M0b-reader-resources.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record));raise SystemExit(result.returncode)
