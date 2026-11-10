import json
import os
from pathlib import Path
import subprocess
import sys

from velowind_appium.triage.allure_results import COMPLETE_MARKER, import_failures, publish
from velowind_appium.triage.store import Store, write_json
from velowind_appium.triage.worker import Worker


def case(results, *, name='test_case[value]', uuid='case-uuid'):
    results.mkdir(parents=True, exist_ok=True)
    value = {'uuid': uuid, 'name': name, 'fullName': 'tests.message.test_example#test_case',
             'status': 'broken', 'statusDetails': {'message': 'Cleanup HTTP 400'},
             'start': 100, 'stop': 200, 'steps': [{'name': 'original assertion', 'status': 'passed'}],
             'attachments': [{'name': 'original screenshot', 'source': 'original.png', 'type': 'image/png'}]}
    (results / 'original.png').write_bytes(b'original screenshot bytes')
    write_json(results / (uuid + '-result.json'), value)
    return value


def test_publish_is_idempotent_preserves_original_and_keeps_each_diagnosis(tmp_path):
    results = tmp_path / 'allure-results'
    original = case(results)
    other = case(results, name='test_other', uuid='other-uuid')
    # Only import the selected case for this test.
    store = Store(tmp_path / 'queue')
    ids = import_failures(store, results)
    job_id = next(x for x in ids if store.get(x)['payload']['metadata']['allure_uuid'] == 'case-uuid')
    store.update(job_id, 'needs_human', diagnosis={'category': 'unknown', 'summary': 'Evidence insufficient'}, reason='review evidence')
    assert publish(store, store.get(job_id))['status'] == 'published'
    attached = json.loads((results / 'case-uuid-result.json').read_text())
    for key in ('status', 'statusDetails', 'start', 'stop', 'steps'):
        assert attached[key] == original[key]
    assert attached['attachments'][0] == original['attachments'][0]
    assert json.loads((results / 'other-uuid-result.json').read_text()) == other
    assert publish(store, store.get(job_id))['status'] == 'unchanged'
    assert len(attached['attachments']) == 3
    store.update(job_id, 'needs_human', diagnosis={'category': 'automation_defect', 'summary': 'New evidence'}, reason='dirty source')
    assert publish(store, store.get(job_id))['status'] == 'published'
    attached = json.loads((results / 'case-uuid-result.json').read_text())
    assert len(attached['attachments']) == 5
    assert 'Evidence insufficient' in (results / attached['attachments'][1]['source']).read_text()
    assert 'New evidence' in (results / attached['attachments'][3]['source']).read_text()


def test_import_deduplicates_and_never_reads_parent_attachments(tmp_path):
    results = tmp_path / 'allure-results'
    original = case(results)
    original['attachments'].append({'name': 'unsafe', 'source': '../secret.xml', 'type': 'application/xml'})
    write_json(results / 'case-uuid-result.json', original)
    (tmp_path / 'secret.xml').write_text('must not copy')
    store = Store(tmp_path / 'queue')
    jobs = import_failures(store, results)
    assert len(jobs) == 1
    assert import_failures(store, results) == []
    payload = store.get(jobs[0])['payload']
    assert payload['dirty'] is True
    assert payload['commit'] == 'unknown'
    assert payload['nodeid'].endswith('tests/message/test_example.py::test_case[value]')
    assert set(payload['artifacts']) == {'PNG'}
    assert json.loads((results / 'case-uuid-result.json').read_text()) == original


def test_live_result_waits_for_session_finish_and_matches_exact_label(tmp_path):
    store = Store(tmp_path / 'queue')
    results = tmp_path / 'allure-results'
    results.mkdir()
    job_id = store.enqueue(dict(nodeid='tests/test_example.py::test_case', phase='call', error='failed', platform='ios',
                               metadata={'allure_results_dir': str(results)}, artifacts={}))
    store.update(job_id, 'needs_human', reason='manual')
    assert publish(store, store.get(job_id))['status'] == 'pending'
    data = case(results)
    data['labels'] = [{'name': 'triageJobId', 'value': job_id}]
    write_json(results / 'case-uuid-result.json', data)
    assert publish(store, store.get(job_id))['status'] == 'pending'
    write_json(results / COMPLETE_MARKER, {'exitstatus': 1})
    assert publish(store, store.get(job_id))['status'] == 'published'


def test_real_pytest_failure_has_job_label_and_can_receive_diagnosis(tmp_path):
    package = str(Path(__file__).resolve().parents[2])
    source = tmp_path / 'test_sample.py'
    source.write_text('def test_failure():\n    assert False, "synthetic framework validation"\n')
    results = tmp_path / 'allure-results'
    queue = tmp_path / 'queue'
    env = dict(os.environ, PYTHONPATH=package, VW_APPIUM_TRIAGE_ENABLED='true', VW_APPIUM_TRIAGE_DIR=str(queue), VW_APPIUM_TRIAGE_AUTOSTART='false')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'velowind_appium.pytest_failure_triage',
                             '-q', str(source), '--alluredir=' + str(results)],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 1, result.stdout + result.stderr
    store = Store(queue)
    assert len(store.list()) == 1
    job = store.get(store.list()[0]['id'])
    data = json.loads(next(results.glob('*-result.json')).read_text())
    assert {'name': 'triageJobId', 'value': job['id']} in data['labels']
    assert (results / COMPLETE_MARKER).exists()
    assert job['payload']['metadata']['allure_results_dir'] == str(results)
    store.update(job['id'], 'needs_human', reason='integration probe')
    assert publish(store, store.get(job['id']))['status'] == 'published'
    assert len(import_failures(store, results)) == 0


def test_once_empty_queue_prints_feedback_and_respects_environment_queue(tmp_path):
    package = str(Path(__file__).resolve().parents[2])
    config = tmp_path / 'config.json'
    config.write_text('{}')
    queue = tmp_path / 'custom-queue'
    env = dict(os.environ, PYTHONPATH=package, VW_APPIUM_TRIAGE_DIR=str(queue), VW_APPIUM_TRIAGE_AUTOSTART='false')
    result = subprocess.run([sys.executable, '-m', 'velowind_appium.triage', '--config', str(config), 'once'],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert str(queue) in result.stdout
    assert '队列为空' in result.stdout
    assert '不会调用 AI' in result.stdout
    assert '0 个任务' in result.stdout


def test_busy_worker_reports_instead_of_duplicate_model_call(tmp_path):
    class NoAgent:
        def ask(self, *args):
            raise AssertionError('Must not call model while another worker holds lock')
    repo = Path(__file__).resolve().parents[5]
    messages = []
    worker = Worker(repo, tmp_path / 'queue', {}, NoAgent(), reporter=messages.append)
    worker.store.enqueue(dict(nodeid='test_case', phase='call', error='failure', platform='ios', artifacts={}))
    with Store(tmp_path / 'queue').lock():
        assert worker.tick() == []
    assert any('其他 worker' in line for line in messages)
