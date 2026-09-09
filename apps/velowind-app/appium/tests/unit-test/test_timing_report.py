import json
import os
from pathlib import Path
import subprocess
import sys

from velowind_appium.timing_report import import_allure, write_report


def test_historical_import_preserves_failure_nested_steps_and_unknown_total(tmp_path):
    (tmp_path / 'one-result.json').write_text(json.dumps({
        'name': 'case[value]', 'fullName': 'tests.test_case#case', 'status': 'failed',
        'start': 1000, 'stop': 5000, 'steps': [{'name': 'parent', 'status': 'failed',
        'start': 1000, 'stop': 4000, 'steps': [{'name': 'child', 'status': 'passed', 'start': 2000, 'stop': 3000}]}]}))
    report = import_allure(tmp_path)
    case = report['cases'][0]
    assert case['total_seconds'] is None
    assert case['phases']['call'] == {'status': 'failed', 'duration_seconds': 4}
    assert [(s['name'], s['depth'], s['duration_seconds']) for s in case['steps']] == [('parent', 0, 3), ('child', 1, 1)]
    write_report(report, tmp_path / 'out')
    assert 'parent' in (tmp_path / 'out/timings.csv').read_text(encoding='utf-8-sig')


def test_pytest_records_setup_call_teardown_failure_skip_and_nested_steps(tmp_path):
    # Isolated synthetic suite avoids the repository's real-device fixtures.
    (tmp_path / 'test_sample.py').write_text('''
import allure
import pytest
from velowind_appium.timing import profile_section
@pytest.fixture
def broken_setup():
    raise RuntimeError('setup fails')
@pytest.fixture
def broken_teardown():
    yield
    raise RuntimeError('teardown fails')
def test_pass():
    with allure.step('outer'):
        with allure.step('inner'):
            with profile_section('internal'):
                pass
def test_fail():
    with allure.step('failed step'):
        assert False
def test_skip():
    pytest.skip('not available')
def test_setup(broken_setup): pass
def test_teardown(broken_teardown): pass
''')
    env = dict(os.environ, VW_APPIUM_TIMING_DIR=str(tmp_path / 'measurements'))
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2])
    result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'velowind_appium.pytest_timing', '-q', str(tmp_path / 'test_sample.py')],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    path = next((tmp_path / 'measurements').glob('*/timings.json'))
    report = json.loads(path.read_text())
    cases = {case['name']: case for case in report['cases']}
    assert [cases[name]['status'] for name in ['test_pass', 'test_fail', 'test_skip', 'test_setup', 'test_teardown']] == ['passed', 'failed', 'skipped', 'failed', 'failed']
    assert set(cases['test_pass']['phases']) == {'setup', 'call', 'teardown'}
    assert [s['name'] for s in cases['test_pass']['steps']] == ['outer', 'inner', 'internal']
    assert cases['test_fail']['steps'][0]['status'] == 'failed'
    events = [json.loads(line) for line in path.with_name('events.jsonl').read_text().splitlines()]
    assert sum(e['event'] == 'case_end' for e in events) == 5
    assert events[-1]['event'] == 'run_end'


def test_comparison_never_labels_skips_failures_missing_cases_as_improvements():
    from copy import deepcopy
    from velowind_appium.timing_report import compare_reports
    baseline = {'measurement': 'allure_wall_clock_ms', 'cases': [
        {'name': name, 'nodeid': name, 'status': 'passed', 'steps': [],
         'phases': {'call': {'status': 'passed', 'duration_seconds': 10}}}
        for name in ['passes', 'fails', 'skips', 'missing']]}
    candidate = deepcopy(baseline)
    candidate['cases'].pop()
    for case, status in zip(candidate['cases'], ['passed', 'failed', 'skipped']):
        case['status'] = status
        case['phases']['call'] = {'status': status, 'duration_seconds': 2}
    rows = compare_reports(baseline, candidate)
    assert [row['comparable'] for row in rows] == [True, False, False, False]
    assert [row['improvement_percent'] for row in rows] == [80, None, None, None]
