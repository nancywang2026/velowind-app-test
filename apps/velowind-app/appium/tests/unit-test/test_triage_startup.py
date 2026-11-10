import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace

import pytest

from velowind_appium import pytest_failure_triage as plugin
from velowind_appium.triage.startup import ensure_worker, watching
from velowind_appium.triage.store import Store


def test_start_reuse_and_restart_real_watcher(tmp_path):
    repo = Path(__file__).resolve().parents[5]
    queue = tmp_path / 'queue'
    config = tmp_path / 'config.json'
    config.write_text('{}')
    pids = []
    try:
        assert '自动启动' in ensure_worker(repo, queue, config)
        pid = json.loads((queue / 'worker-watch.json').read_text())['pid']
        pids.append(pid)
        assert watching(queue)
        assert '已运行' in ensure_worker(repo, queue, config)
        assert json.loads((queue / 'worker-watch.json').read_text())['pid'] == pid
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            if not watching(queue):
                break
            time.sleep(.02)
        assert not watching(queue)
        assert '自动启动' in ensure_worker(repo, queue, config)
        restarted = json.loads((queue / 'worker-watch.json').read_text())['pid']
        pids.append(restarted)
        assert restarted != pid
    finally:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_existing_lifetime_lock_does_not_spawn(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Must reuse existing watcher')
    monkeypatch.setattr('velowind_appium.triage.startup.subprocess.Popen', forbidden)
    with Store(tmp_path).lock('watch'):
        assert '已运行' in ensure_worker(tmp_path, tmp_path)


def test_missing_config_does_not_spawn(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('No configuration, no external process')
    monkeypatch.setattr('velowind_appium.triage.startup.subprocess.Popen', forbidden)
    assert '配置不存在' in ensure_worker(tmp_path, tmp_path / 'queue')


def test_collection_autostart_respects_disable_and_unit_only(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr('velowind_appium.triage.startup.ensure_worker', lambda *a: calls.append(a) or 'started')
    monkeypatch.setenv('VW_APPIUM_TRIAGE_ENABLED', 'true')
    monkeypatch.setenv('VW_APPIUM_TRIAGE_AUTOSTART', 'true')
    monkeypatch.setenv('VW_APPIUM_TRIAGE_DIR', str(tmp_path))
    monkeypatch.setenv('VW_APPIUM_TRIAGE_CONFIG', str(tmp_path / 'config.json'))
    options = SimpleNamespace(option=SimpleNamespace(collectonly=False))
    unit = SimpleNamespace(config=options, items=[SimpleNamespace(fspath='/repo/tests/unit-test/test_sample.py')])
    device = SimpleNamespace(config=options, items=[SimpleNamespace(fspath='/repo/tests/message/test_sample.py')])
    plugin.pytest_collection_finish(unit)
    options.option.collectonly = True
    plugin.pytest_collection_finish(device)
    options.option.collectonly = False
    assert not calls
    monkeypatch.setenv('VW_APPIUM_TRIAGE_ENABLED', 'false')
    plugin.pytest_collection_finish(device)
    assert not calls
    monkeypatch.setenv('VW_APPIUM_TRIAGE_ENABLED', 'true')
    monkeypatch.setenv('VW_APPIUM_TRIAGE_AUTOSTART', 'false')
    plugin.pytest_collection_finish(device)
    assert not calls
    monkeypatch.setenv('VW_APPIUM_TRIAGE_AUTOSTART', 'true')
    plugin.pytest_collection_finish(device)
    assert len(calls) == 1
    assert calls[0][1:] == (tmp_path, str(tmp_path / 'config.json'))
