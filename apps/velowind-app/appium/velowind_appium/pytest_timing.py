"""Pytest timing recorder. JSONL is flushed at every start/end, even before a case finishes."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import time

import pytest

from . import timing
from .allure_artifacts import allure_artifacts
from .timing_report import write_report

try:
    import allure_commons
    from allure_commons import hookimpl
except ImportError:
    allure_commons = None
    def hookimpl(function):
        return function


class TimingRecorder:
    def __init__(self, output: Path, metadata: dict):
        self.output = output
        output.mkdir(parents=True, exist_ok=True)
        # Attempts/workers get separate directories: never overwrite a previous run.
        self.stream = (output / 'events.jsonl').open('x', encoding='utf-8')
        self.report = {'schema_version': 1, 'measurement': 'monotonic_seconds', **metadata, 'cases': []}
        self.current = None
        self.active = {}
        self.stack = []
        self.event('run_start', metadata=metadata)

    def event(self, event, **data):
        self.stream.write(json.dumps({'event': event, 'wall_time_ns': time.time_ns(),
                                      'nodeid': self.current['nodeid'] if self.current else None,
                                      **data}, ensure_ascii=False) + '\n')
        self.stream.flush()

    def begin(self, nodeid, name):
        self.started = time.perf_counter()
        self.current = {'nodeid': nodeid, 'name': name, 'status': 'incomplete', 'phases': {}, 'steps': []}
        self.report['cases'].append(self.current)
        self.event('case_start')

    def phase(self, report):
        if self.current is None:
            return
        self.current['phases'][report.when] = {'status': report.outcome, 'duration_seconds': report.duration}
        self.event('phase_end', phase=report.when, status=report.outcome, duration_seconds=report.duration)

    def end(self):
        phases = self.current['phases']
        statuses = [p['status'] for p in phases.values()]
        self.current['status'] = ('failed' if 'failed' in statuses else 'skipped' if 'skipped' in statuses
                                  else 'passed' if set(phases) == {'setup', 'call', 'teardown'} else 'incomplete')
        self.current['total_seconds'] = time.perf_counter() - self.started
        for uuid in list(self.active):
            self.stop(uuid, 'incomplete')
        self.event('case_end', status=self.current['status'], duration_seconds=self.current['total_seconds'])
        write_report(self.report, self.output)
        self.current = None

    def start(self, uuid, title, kind):
        if self.current is None:
            return
        row = {'name': title, 'kind': kind, 'depth': len(self.stack), 'status': 'incomplete', 'duration_seconds': None}
        self.current['steps'].append(row)
        self.active[uuid] = (time.perf_counter(), row)
        self.stack.append(uuid)
        self.event('step_start', id=uuid, **row)

    def stop(self, uuid, status):
        if uuid not in self.active:
            return
        started, row = self.active.pop(uuid)
        self.stack.remove(uuid)
        row.update(status=status, duration_seconds=time.perf_counter() - started)
        self.event('step_end', id=uuid, **row)

    @hookimpl
    def start_step(self, uuid, title, params):
        self.start(uuid, title, 'step')

    @hookimpl
    def stop_step(self, uuid, exc_type, exc_val, exc_tb):
        status = 'passed' if exc_type is None else 'skipped' if issubclass(exc_type, pytest.skip.Exception) else 'failed'
        self.stop(uuid, status)


def pytest_configure(config):
    root = Path(__file__).resolve().parents[4]
    platform = os.environ.get('VW_APPIUM_PLATFORM', 'ios')
    output = Path(os.environ.get('VW_APPIUM_TIMING_DIR') or allure_artifacts(root, platform).results.parent / 'timing')
    worker = os.environ.get('PYTEST_XDIST_WORKER', 'main')
    output = output / f'{worker}-{os.getpid()}-{time.time_ns()}'
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True, check=False).stdout.strip()
    source_hash = hashlib.sha256()
    appium_root = Path(__file__).resolve().parents[1]
    for path in sorted(appium_root.rglob('*.py')):
        source_hash.update(str(path.relative_to(appium_root)).encode())
        source_hash.update(path.read_bytes())
    recorder = TimingRecorder(output, {'platform': platform, 'git_commit': commit,
                                      'python_sources_sha256': source_hash.hexdigest(),
                                      'argv': list(config.invocation_params.args),
                                      'worker': worker, 'run_id': os.environ.get('VW_APPIUM_RUN_ID')})
    config._appium_timing = recorder
    timing.recorder = recorder
    if allure_commons is not None:
        allure_commons.plugin_manager.register(recorder)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    recorder = item.config._appium_timing
    recorder.begin(item.nodeid, item.name)
    try:
        yield
    finally:
        recorder.end()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    result = yield
    recorder = item.config._appium_timing
    recorder.phase(result.get_result())
    app_config = item.funcargs.get('ios_config') or item.funcargs.get('android_config')
    if app_config is not None and 'device' not in recorder.report:
        recorder.report['device'] = {
            name: str(getattr(app_config, name, '') or '')
            for name in ('target', 'udid', 'device_name', 'platform_version', 'server_url', 'app_package', 'bundle_id', 'app_path')
        }
        recorder.event('device', metadata=recorder.report['device'])


def pytest_sessionfinish(session, exitstatus):
    recorder = session.config._appium_timing
    recorder.report['exitstatus'] = int(exitstatus)
    recorder.event('run_end', exitstatus=int(exitstatus))
    write_report(recorder.report, recorder.output)
    print(f'\n[appium-timing] {recorder.output}')


def pytest_unconfigure(config):
    recorder = getattr(config, '_appium_timing', None)
    if recorder is not None:
        if allure_commons is not None:
            allure_commons.plugin_manager.unregister(recorder)
        if timing.recorder is recorder:
            timing.recorder = None
        recorder.stream.close()
