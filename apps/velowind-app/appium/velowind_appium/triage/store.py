from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid

APP = 'apps/velowind-app/appium'


def redact(text):
    text = str(text)
    text = re.sub(r'\bsk-[A-Za-z0-9_*\-]{8,}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', text)
    text = re.sub(r'''(?ix)(["']?(?:password|passwd|token|access_token|refresh_token|authorization|cookie|secret|api_key)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''', r'\1"[REDACTED]"', text)
    text = re.sub(r'\b1[3-9]\d{9}\b', '[PHONE]', text)
    return re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


class QueueBusyError(RuntimeError):
    pass


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(str(self.root / 'queue.sqlite3'), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, fingerprint TEXT, state TEXT, payload TEXT,
            result TEXT, created REAL, updated REAL)''')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, state TEXT, result TEXT, created REAL)')
        self.db.commit()

    def enqueue(self, payload):
        job_id = uuid.uuid4().hex
        fingerprint = hashlib.sha256(json.dumps([
            payload.get('commit'), payload.get('dirty_hash'), payload['nodeid'],
            payload['phase'], payload['platform'], payload['error'].splitlines()[-1:]
        ], sort_keys=True).encode()).hexdigest()[:24]
        import shutil
        snapshots = {}
        job_dir = self.root / job_id
        job_dir.mkdir(mode=0o700)
        for kind, original in payload.get('artifacts', {}).items():
            original = Path(original)
            if original.is_file() and kind in {'PNG', 'XML'}:
                dest = job_dir / ('failure.' + kind.lower())
                if kind == 'XML':
                    dest.write_text(redact(original.read_text(encoding='utf-8')))
                else:
                    shutil.copyfile(original, dest)
                os.chmod(dest, 0o600)
                snapshots[kind] = str(dest)
        source_contents = payload.pop('_source_contents', None)
        if source_contents is not None:
            write_json(job_dir / 'source-snapshot.json', source_contents)
        payload = dict(payload, artifacts=snapshots)
        now = time.time()
        self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',
                        (job_id, fingerprint, 'queued', json.dumps(payload), '{}', now, now))
        self.db.execute('INSERT INTO events (job_id,state,result,created) VALUES (?,?,?,?)', (job_id, 'queued', '{}', now))
        self.db.commit()
        write_json(self.root / job_id / 'failure.json', payload)
        return job_id

    def get(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise ValueError('Unknown job')
        result = dict(row)
        for key in ('payload', 'result'):
            result[key] = json.loads(result[key])
        return result

    def update(self, job_id, state, **result):
        current = self.get(job_id)['result']
        current.update(result)
        self.db.execute('UPDATE jobs SET state=?, result=?, updated=? WHERE id=?',
                        (state, json.dumps(current), time.time(), job_id))
        self.db.execute('INSERT INTO events (job_id,state,result,created) VALUES (?,?,?,?)',
                        (job_id, state, json.dumps(current), time.time()))
        self.db.commit()
        write_json(self.root / job_id / 'result.json', dict(state=state, **current))

    def history(self, job_id):
        return [dict(row, result=json.loads(row['result'])) for row in self.db.execute(
            'SELECT * FROM events WHERE job_id=? ORDER BY event_id', (job_id,))]

    def list(self):
        return [dict(row) for row in self.db.execute(
            'SELECT id, fingerprint, state, updated FROM jobs ORDER BY created')]

    @contextlib.contextmanager
    def lock(self, name='worker'):
        # Kernel releases flock after a crash; do not delete the shared lock inode.
        import fcntl
        with (self.root / (name + '.lock')).open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise QueueBusyError('Another triage worker owns this queue/device lock')
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def enqueue_failure(repo, queue, nodeid, phase, error, platform, artifacts=None, metadata=None, source_snapshot=None):
    repo = Path(repo).resolve()
    status = git(repo, 'status', '--porcelain', '--untracked-files=normal')
    diff = git(repo, 'diff', 'HEAD', '--binary')
    snapshot = source_snapshot or {}
    commit = git(repo, 'rev-parse', 'HEAD')
    dirty_hash = hashlib.sha256((status + diff).encode()).hexdigest() if status else None
    from .evidence import capture_sources
    current_sources = capture_sources(repo)
    content_drift = bool(snapshot.get('files') is not None and {k: v['original_sha256'] for k, v in snapshot['files'].items()} != {k: v['original_sha256'] for k, v in current_sources['files'].items()})
    drifted = content_drift or bool(snapshot and (snapshot['commit'] != commit or snapshot['dirty_hash'] != dirty_hash))
    payload = dict(nodeid=nodeid, phase=phase, error=redact(error), platform=platform,
                   commit=snapshot.get('commit', commit), dirty=bool(status) or bool(snapshot.get('dirty')) or drifted,
                   source_changed_during_run=drifted, dirty_hash=dirty_hash,
                   artifacts={str(k): str(Path(v).resolve()) for k, v in (artifacts or {}).items()},
                   metadata=metadata or {}, cleanup='unknown', device_validation='failed')
    if snapshot.get('files') is not None:
        payload['_source_contents'] = {k: snapshot[k] for k in ['files', 'missing', 'kind']}
    elif not source_snapshot:
        payload['_source_contents'] = current_sources
        payload['_source_contents']['kind'] = 'failure-capture; no session-start snapshot'
    store = Store(queue)
    try:
        return store.enqueue(payload)
    finally:
        store.db.close()
