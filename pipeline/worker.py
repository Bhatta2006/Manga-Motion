"""Run one durable chapter job in an isolated process, then release its memory."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

from pipeline.db import Jobs
from pipeline.runtime.scheduler import _single_heavy_model, StageExecutionError
from pipeline.store import ChapterStore, read_json
from pipeline.ingest.hashes import object_hash


def execute_job(jobs, job, library, runtime, *, importer=None, analyzer=None, compiler=None, publisher=None):
    # Import heavy adapter modules only in the child, after it has claimed the job.
    if importer is None:
        from pipeline.ingest.chapter import import_chapter
        importer = import_chapter
    if analyzer is None:
        from pipeline.analyze_chapter import analyze_chapter
        analyzer = analyze_chapter
    if compiler is None:
        from pipeline.build_motion import build_motion
        compiler = build_motion
    if publisher is None:
        from pipeline.api.chapters import playback_info
        publisher = playback_info
    request = job['request']
    store = ChapterStore(library, job['series'], job['chapter'])
    checkpoint, metrics = job['checkpoint'], job['metrics']
    started = time.perf_counter()

    def progress(value):
        jobs.update(job['id'], phase=value['stage'], progress=value)

    try:
        manifest = read_json(store.asset('import.json'))
        if not checkpoint.get('import_hash') or object_hash(manifest) != checkpoint['import_hash']:
            jobs.update(job['id'], phase='import', progress={})
            manifest, metrics['import'] = importer(Path(request['source']), library, job['series'], job['chapter'],
                                                   overrides=request['settings'])
            checkpoint['import_hash'] = object_hash(manifest)
            jobs.update(job['id'], checkpoint=checkpoint, metrics=metrics)
        else:
            metrics['import_resumed'] = True
        from pipeline.streaming import StreamingPublisher
        stream=StreamingPublisher(store,manifest) if manifest.get('import_manifest_version')==1 else None
        def ready(page):
            if stream:
                stream.publish(page)
                metrics['streaming']=stream.metrics
                if 'first_readable_seconds' not in metrics:
                    metrics['first_readable_seconds']=round(time.perf_counter()-started,6)
                jobs.update(job['id'],metrics=metrics)
        jobs.update(job['id'], phase='analysis', progress={})
        _, metrics['analysis'] = analyzer(library, job['series'], job['chapter'], runtime, progress=progress,page_ready=ready)
        jobs.update(job['id'], metrics=metrics)
        jobs.update(job['id'], phase='camera', progress={})
        _, metrics['camera'] = compiler(library, job['series'], job['chapter'], runtime, progress=progress)
        jobs.update(job['id'], phase='publishing', metrics=metrics)
        info = publisher(store)
        metrics['worker_seconds'] = round(time.perf_counter()-started, 6)
        metrics.setdefault('first_readable_seconds',metrics['worker_seconds'])
        metrics['playback'] = info
        jobs.update(job['id'], status='completed', phase='completed', progress={}, metrics=metrics)
        return True
    except Exception as exc:
        if isinstance(exc, StageExecutionError): metrics['failed_stage'] = exc.metrics
        metrics['attempt_seconds'] = round(time.perf_counter()-started, 6)
        jobs.update(job['id'], status='failed', error=f'{type(exc).__name__}: {exc}', metrics=metrics)
        traceback.print_exc()
        return False


def run_once(library: Path, runtime: Path, execute=execute_job):
    # One lock across all chapter DBs on this machine; before recovery and model imports.
    try:
        with _single_heavy_model(runtime/'job-worker.lock', timeout_seconds=1):
            jobs = Jobs(library/'jobs.sqlite3')
            job = jobs.recover_and_claim()
            if job is None: return 0
            return 0 if execute(jobs, job, library, runtime) else 2
    except TimeoutError:
        return 75


class WorkerCoordinator:
    """API thread supervises one child; it never imports or loads a model."""
    def __init__(self, library, runtime):
        self.library, self.runtime = library, runtime
        self.jobs = Jobs(library/'jobs.sqlite3')
        self.stop_event = threading.Event()
        self.child = None
        self.thread = threading.Thread(target=self.run, name='chapter-coordinator', daemon=True)
        self.last_error = None

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            try:
                if self.jobs.pending():
                    logs = self.runtime/'logs'
                    if not logs.resolve().is_relative_to(self.runtime.resolve()): raise ValueError('Worker log path escapes the D-drive runtime')
                    logs.mkdir(parents=True, exist_ok=True)
                    with (logs/f'worker-{uuid.uuid4().hex}.log').open('wb') as log:
                        self.child = subprocess.Popen([sys.executable, '-m', 'pipeline.worker', '--once',
                                                       '--library', str(self.library), '--runtime', str(self.runtime)],
                            cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                        while self.child.poll() is None and not self.stop_event.wait(.2): pass
                        if self.stop_event.is_set() and self.child.poll() is None:
                            self.child.terminate()
                            try: self.child.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                self.child.kill(); self.child.wait(timeout=5)
                    self.child = None
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
            self.stop_event.wait(1)

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    for path in (args.library,args.runtime):
        if path.resolve().drive.upper() != 'D:': parser.error('Worker paths must be on D:')
    return run_once(args.library.resolve(), args.runtime.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
