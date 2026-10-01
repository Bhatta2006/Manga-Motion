"""Durable chapter jobs. Connections are short lived; no models in the API."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class JobConflict(ValueError):
    pass


class Jobs:
    def __init__(self, path: Path):
        parent = path.parent.resolve()
        if parent.drive.upper() != 'D:': raise ValueError('Job database must stay on D:')
        for candidate in (path,Path(str(path)+'-wal'),Path(str(path)+'-shm'),Path(str(path)+'-journal')):
            if not candidate.resolve().is_relative_to(parent): raise ValueError('Linked database paths are not allowed')
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, series TEXT NOT NULL, chapter TEXT NOT NULL,
                    request TEXT NOT NULL, status TEXT NOT NULL,
                    phase TEXT NOT NULL, progress TEXT NOT NULL DEFAULT '{}',
                    checkpoint TEXT NOT NULL DEFAULT '{}', metrics TEXT NOT NULL DEFAULT '{}',
                    attempts INTEGER NOT NULL DEFAULT 0, recoveries INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL, error TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_chapter
                    ON jobs(series, chapter) WHERE status IN ('queued','running');
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_chapter_case
                    ON jobs(series COLLATE NOCASE, chapter COLLATE NOCASE) WHERE status IN ('queued','running');
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        for key in ('request', 'progress', 'checkpoint', 'metrics'):
            result[key] = json.loads(result[key])
        return result

    def get(self, job_id):
        with self.connection() as db:
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def list(self):
        with self.connection() as db:
            return [self.decode(row) for row in db.execute('SELECT * FROM jobs ORDER BY created DESC,id')]

    def enqueue(self, request):
        encoded = json.dumps(request, sort_keys=True)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute("SELECT * FROM jobs WHERE series=? COLLATE NOCASE AND chapter=? COLLATE NOCASE AND status IN ('queued','running')",
                                (request['series'], request['chapter'])).fetchone()
            if active:
                if active['request'] != encoded:
                    raise JobConflict('This chapter already has a different active import')
                return self.decode(active)
            job_id, now = uuid.uuid4().hex, time.time()
            db.execute('INSERT INTO jobs(id,series,chapter,request,status,phase,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                       (job_id, request['series'], request['chapter'], encoded, 'queued', 'queued', now, now))
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def recover_and_claim(self):
        """Caller MUST hold the OS worker lock; live workers cannot be recovered."""
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            # One automatic resume after a process interruption; repeated crashes need explicit retry.
            db.execute("UPDATE jobs SET status=CASE WHEN recoveries<1 THEN 'queued' ELSE 'failed' END, "
                       "phase='interrupted', error='Worker interrupted; cached stages are retained', "
                       "recoveries=recoveries+1, updated=? WHERE status='running'", (time.time(),))
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running', phase='starting', error=NULL, attempts=attempts+1, updated=? WHERE id=?",
                       (time.time(), row['id']))
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone())

    def update(self, job_id, **fields):
        allowed = {'status', 'phase', 'progress', 'checkpoint', 'metrics', 'error'}
        if not fields or not fields.keys() <= allowed:
            raise ValueError('Invalid job update')
        values = [json.dumps(v, sort_keys=True) if k in {'progress','checkpoint','metrics'} else v for k,v in fields.items()]
        with self.connection() as db:
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+',updated=? WHERE id=?',
                       (*values, time.time(), job_id))

    def retry(self, job_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row['status'] != 'failed':
                raise JobConflict('Only failed jobs can be retried')
            try:
                db.execute("UPDATE jobs SET status='queued',phase='queued',progress='{}',error=NULL,recoveries=0,updated=? WHERE id=?",
                           (time.time(), job_id))
            except sqlite3.IntegrityError as exc:
                raise JobConflict('This chapter already has an active job') from exc
            return self.decode(db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def pending(self):
        with self.connection() as db:
            return db.execute("SELECT EXISTS(SELECT 1 FROM jobs WHERE status IN ('queued','running'))").fetchone()[0] == 1
