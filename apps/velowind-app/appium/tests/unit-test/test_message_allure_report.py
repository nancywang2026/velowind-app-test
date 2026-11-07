import json
from pathlib import Path

import pytest

from velowind_appium.message_regression.allure_report import export_record


def test_preserves_status_evidence_and_missing_timestamps(tmp_path):
    source = tmp_path / 'suite' / 'live-results.json'
    source.parent.mkdir()
    (source.parent / 'failure.xml').write_text('<Appium/>')
    record = {'run_id': 'original', 'accounts': {'password': 'SECRET'}, 'cases': [
        {'name': 'private.pass', 'status': 'passed', 'seconds': 1.2},
        {'name': 'private.fail', 'status': 'failed', 'reason': '27px drift'},
        {'name': 'private.blocked', 'status': 'blocked', 'reason': 'Unavailable'},
        {'name': 'private.running', 'status': 'running'},
    ]}
    out = tmp_path / 'allure-results'
    assert export_record(record, source, out) == 3
    results = [json.loads(p.read_text()) for p in out.glob('*-result.json')]
    assert sorted(r['status'] for r in results) == ['failed', 'passed', 'skipped']
    assert all('start' not in r and 'stop' not in r for r in results)
    assert all(len(r['attachments']) == 2 for r in results)
    assert all((out / a['source']).exists() for r in results for a in r['attachments'])
    assert 'SECRET' not in ''.join(p.read_text() for p in out.iterdir())
    export_record(record, source, out)
    assert len(list(out.glob('*-result.json'))) == 3


def test_retains_actual_timestamps(tmp_path):
    row = {'name': 'private.timed', 'status': 'passed', 'start': 1000, 'stop': 2500}
    export_record({'cases': [row]}, tmp_path / 'live-results.json', tmp_path / 'results')
    result = json.loads(next((tmp_path / 'results').glob('*-result.json')).read_text())
    assert (result['start'], result['stop']) == (1000, 2500)
    assert len(result['attachments']) == 1


def test_rejects_unknown_state(tmp_path):
    with pytest.raises(KeyError):
        export_record({'cases': [{'name': 'unknown', 'status': 'unexpected'}]},
                      tmp_path / 'live-results.json', tmp_path / 'results')


def test_live_run_automatically_exports_success_and_failure(tmp_path):
    from types import SimpleNamespace
    from velowind_appium.message_regression.live import LiveRun

    run = LiveRun.__new__(LiveRun)
    run.output = tmp_path
    run.api = SimpleNamespace(journal=[])
    run.report = {'run_id': 'offline', 'cases': [], 'resources': []}
    with run.case('private.success'):
        pass
    with pytest.raises(AssertionError):
        with run.case('private.failure'):
            raise AssertionError('Read icon mismatch')
    rows = [json.loads(p.read_text()) for p in (tmp_path / 'allure-results').glob('*-result.json')]
    assert sorted(r['status'] for r in rows) == ['failed', 'passed']
    assert all(r['stop'] >= r['start'] > 0 for r in rows)
    assert json.loads((tmp_path / 'live-results.json').read_text())['cases'][1]['status'] == 'failed'


def test_private_report_has_descriptions_and_case_specific_screenshots(tmp_path):
    from velowind_appium.message_regression.case_descriptions import PRIVATE_CASES
    source = tmp_path / 'live-results.json'
    png = b'\x89PNG\r\n\x1a\nfixture'
    (tmp_path / 'only-this-case.png').write_bytes(png)
    record = {'cases': [{'name': name, 'status': 'failed',
                        'screenshots': [{'path': 'only-this-case.png', 'name': '失败现场'}]}
                       for name in PRIVATE_CASES]}
    export_record(record, source, tmp_path / 'results')
    for result_file in (tmp_path / 'results').glob('*-result.json'):
        result = json.loads(result_file.read_text())
        assert all(label in result['description'] for label in ('测试内容', '准备数据', '执行步骤', '验证点'))
        assert any(a['type'] == 'image/png' for a in result['attachments'])
        assert result['status'] == 'failed'


def test_screenshot_failure_preserves_original_assertion(tmp_path):
    from types import SimpleNamespace
    from velowind_appium.message_regression.live import LiveRun
    run = LiveRun.__new__(LiveRun)
    run.output = tmp_path
    run.api = SimpleNamespace(journal=[])
    run.report = {'cases': []}
    def capture(*args):
        raise OSError('Unavailable')
    run.capture_evidence = capture
    with pytest.raises(AssertionError, match='Original failure'):
        with run.case('private.native-read-icon'):
            raise AssertionError('Original failure')
    assert run.report['cases'][0]['screenshot_error'] == 'OSError'
    assert run.report['cases'][0]['status'] == 'failed'


def test_native_screenshot_uses_actual_appium_response(tmp_path):
    import base64
    from velowind_appium.message_regression.ios_live import OwnedIOS
    ui = OwnedIOS.__new__(OwnedIOS)
    png = b'\x89PNG\r\n\x1a\nfixture'
    ui.call = lambda path: base64.b64encode(png).decode() if path == '/screenshot' else '<Appium/>'
    ui.snapshot(tmp_path, 'captured')
    assert (tmp_path / 'captured.png').read_bytes() == png
    assert (tmp_path / 'captured.xml').read_text() == '<Appium/>'


def test_phase_screenshot_is_bound_only_to_running_case(tmp_path):
    import base64
    from types import SimpleNamespace
    from velowind_appium.message_regression.ios_live import OwnedIOS
    ui = OwnedIOS.__new__(OwnedIOS)
    ui.call = lambda path: base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode() if path == '/screenshot' else '<Appium/>'
    run = SimpleNamespace(report={'cases': [{'name': 'old', 'status': 'passed'},
                                          {'name': 'current', 'status': 'running'}]})
    ui.bind_evidence(run)
    ui.snapshot(tmp_path, 'before-incoming')
    assert 'screenshots' not in run.report['cases'][0]
    assert run.report['cases'][1]['screenshots'][0]['path'] == 'before-incoming.png'


def test_screenshot_outside_suite_rejected(tmp_path):
    row = {'name': 'private.native-read-icon', 'status': 'failed',
           'screenshots': [{'path': '../outside.png', 'name': 'bad'}]}
    with pytest.raises(ValueError, match='inside this suite'):
        export_record({'cases': [row]}, tmp_path / 'suite' / 'live-results.json', tmp_path / 'results')
