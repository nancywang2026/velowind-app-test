"""Collect only; AI runs out of process after pytest. Never masks test failures."""
import os
from pathlib import Path
import sys

import pytest

from .triage.store import enqueue_failure, git, redact, write_json
from .triage.allure_results import COMPLETE_MARKER


def queue_report(item, report, artifacts=None):
    if not report.failed or '/unit-test/' in str(item.fspath):
        return
    if os.environ.get('VW_APPIUM_TRIAGE_ENABLED', 'true').lower() not in {'true', '1', 'yes'}:
        return
    repo = Path(__file__).resolve().parents[4]
    queue = Path(os.environ.get('VW_APPIUM_TRIAGE_DIR', repo / '.tmp/appium-triage'))
    try:
        try:
            nodeid = str(Path(item.fspath).resolve().relative_to(repo)) + ('::' + item.nodeid.split('::', 1)[1] if '::' in item.nodeid else '')
        except ValueError:
            nodeid = item.nodeid
        config = item.funcargs.get('ios_config')
        driver = item.funcargs.get('driver')
        selection = getattr(driver, '_environment_login_selection', None)
        capabilities = getattr(driver, 'capabilities', {}) or {}
        results_option = getattr(item.config.option, 'allure_report_dir', None)
        results = Path(results_option).resolve() if results_option else None
        job_id = enqueue_failure(repo, queue, nodeid, report.when, str(report.longrepr),
                        os.environ.get('VW_APPIUM_PLATFORM', 'ios'), artifacts,
                        {'allure_results_dir': str(results) if results else None,
                         'allure_report_dir': str(Path(os.environ['VW_ALLURE_REPORT_DIR']).resolve()) if os.environ.get('VW_ALLURE_REPORT_DIR') else (str(results.parent / 'allure-report') if results else None),
                         'run_id': os.environ.get('VW_APPIUM_RUN_ID'),
                         'failed_step': getattr(item, '_failure_triage_step', None),
                         'app_id': getattr(config, 'bundle_id', None) or getattr(config, 'app_package', None),
                         'platform_version': getattr(config, 'platform_version', None),
                         'app_version': capabilities.get('appium:appVersion') or capabilities.get('appVersion'),
                         'observed_environment': getattr(selection, 'environment', None),
                         'device': os.environ.get('VW_IOS_UDID') or os.environ.get('VW_ANDROID_UDID') or getattr(config, 'udid', None)},
                        source_snapshot=getattr(item.session, '_triage_source_snapshot', None))
        print('[triage] 失败已入队：' + job_id + '；队列：' + str(queue.resolve()), flush=True)
        if results:
            try:
                import allure
                import json
                allure.dynamic.label('triageJobId', job_id)
                allure.attach(json.dumps({'job_id': job_id, 'state': 'queued', 'queue': str(queue.resolve())}),
                              name='AI 诊断任务（等待 worker）', attachment_type=allure.attachment_type.JSON)
            except Exception as error:
                print('[triage] 任务已保留，Allure 关联失败：' + type(error).__name__, file=sys.stderr)
    except Exception as error:
        print('Failure triage could not enqueue: ' + type(error).__name__ + ': ' + redact(str(error))[:250], file=sys.stderr)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    # The existing conftest capture hook runs first and associates exact evidence.
    artifacts = getattr(item, '_failure_triage_artifacts', {}).get(report.when, {})
    queue_report(item, report, artifacts)


def pytest_sessionstart(session):
    enabled = os.environ.get('VW_APPIUM_TRIAGE_ENABLED', 'true').lower() in {'true', '1', 'yes'}
    queue = Path(os.environ.get('VW_APPIUM_TRIAGE_DIR', Path(__file__).resolve().parents[4] / '.tmp/appium-triage')).resolve()
    print('[triage] 失败入队：' + ('开启' if enabled else '关闭') + '；队列：' + str(queue), flush=True)
    if not enabled:
        return
    import hashlib
    repo = Path(__file__).resolve().parents[4]
    try:
        status = git(repo, 'status', '--porcelain', '--untracked-files=normal')
        diff = git(repo, 'diff', 'HEAD', '--binary')
        from .triage.evidence import capture_sources
        session._triage_source_snapshot = dict(capture_sources(repo), **{
            'commit': git(repo, 'rev-parse', 'HEAD'), 'dirty': bool(status),
            'dirty_hash': hashlib.sha256((status + diff).encode()).hexdigest() if status else None})
    except Exception:
        # Missing snapshot must not silently imply an exact clean source.
        session._triage_source_snapshot = {'commit': 'unknown', 'dirty': True, 'dirty_hash': None}


def pytest_sessionfinish(session, exitstatus):
    results = getattr(session.config.option, 'allure_report_dir', None)
    if results:
        try:
            write_json(Path(results).resolve() / COMPLETE_MARKER, {
                'exitstatus': int(exitstatus),
                'triage_enabled': os.environ.get('VW_APPIUM_TRIAGE_ENABLED', 'true').lower() in {'true', '1', 'yes'}})
        except Exception as error:
            print('[triage] Allure 完成标记写入失败：' + type(error).__name__, file=sys.stderr)


def pytest_collection_finish(session):
    # Collection identifies unit-only runs without starting an idle external worker.
    if session.config.option.collectonly:
        return
    if os.environ.get('VW_APPIUM_TRIAGE_ENABLED', 'true').lower() not in {'true', '1', 'yes'}:
        return
    if os.environ.get('VW_APPIUM_TRIAGE_AUTOSTART', 'true').lower() not in {'true', '1', 'yes'}:
        return
    if not any('/unit-test/' not in str(item.fspath) for item in session.items):
        return
    from .triage.startup import ensure_worker
    repo = Path(__file__).resolve().parents[4]
    queue = Path(os.environ.get('VW_APPIUM_TRIAGE_DIR', repo / '.tmp/appium-triage'))
    try:
        print('[triage] ' + ensure_worker(repo, queue, os.environ.get('VW_APPIUM_TRIAGE_CONFIG')), flush=True)
    except Exception as error:
        print('[triage] AI worker 自动启动失败：' + redact(str(error))[:250], file=sys.stderr)
