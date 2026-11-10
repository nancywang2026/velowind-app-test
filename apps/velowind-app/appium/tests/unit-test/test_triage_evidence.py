"""Evidence boundary and routing behavior; no devices, network or business writes."""
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from velowind_appium.triage.evidence import Evidence, capture_sources, has_blockers
from velowind_appium.triage.agent import validate_decision
from velowind_appium.triage.store import APP, Store, enqueue_failure, write_json
from velowind_appium.triage.worker import Worker
from test_failure_triage import repository, decision, Agent


def fixture(tmp_path, error='failed'):
    repo, target = repository(tmp_path)
    job_id = enqueue_failure(repo, tmp_path / 'queue', APP + '/tests/unit-test/test_sample.py::test_expected',
                             'call', error, 'android')
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    return repo, target, store, job_id, ev


def v2(**changes):
    result = decision(recommendations=['Inspect selector entry'], candidate_causes=[], evidence_requests=[])
    result.update(changes)
    return result


def request(kind, path='', symbol='', version='failure'):
    return dict(kind=kind, path=path, symbol=symbol, version=version, reason='Resolve locator hypothesis')


def test_late_function_and_imported_dependency_are_complete(tmp_path):
    repo, target = repository(tmp_path)
    dep = target.parent / 'picker.py'
    dep.write_text('def select():\n    return "selected"\n')
    target.write_text('from velowind_appium.modules import picker\n' + '# padding\n' * 6000 +
                      'def late():\n    return picker.select()\n')
    job_id = enqueue_failure(repo, tmp_path / 'queue', APP + '/tests/unit-test/test_sample.py::test_expected',
                             'call', str(target.relative_to(repo)) + ':6003: AssertionError', 'android')
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    items = ev.initial()['evidence']
    late = next(x for x in items if x.get('symbol') == 'late')
    assert late['content'] == 'def late():\n    return picker.select()'
    assert late['start'] > 6000
    assert any(x.get('symbol') == 'select' and 'return "selected"' in x['content'] for x in items)
    assert all(x.get('file_sha256') for x in items if x['kind'] == 'source_function' and x['status'] == 'obtained')


def test_snapshot_keeps_dirty_and_untracked_source_and_detects_drift(tmp_path):
    repo, target = repository(tmp_path)
    target.write_text('def locate():\n    return "dirty-start"\n')
    snapshot = dict(capture_sources(repo), commit=__import__('velowind_appium.triage.store', fromlist=['git']).git(repo, 'rev-parse', 'HEAD'),
                    dirty=True, dirty_hash='different')
    target.write_text('def locate():\n    return "changed-after-start"\n')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'android', source_snapshot=snapshot)
    store = Store(tmp_path / 'queue')
    assert store.get(job_id)['payload']['source_changed_during_run'] is True
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    ev.file(str(target.relative_to(repo)), 'locate')
    assert 'dirty-start' in ev.items[0]['content']
    assert 'changed-after-start' not in ev.items[0]['content']


def test_historical_dirty_source_is_not_replaced_by_head(tmp_path):
    repo, target, store, job_id, _ = fixture(tmp_path)
    (store.root / job_id / 'source-snapshot.json').unlink()
    job = store.get(job_id)
    job['payload']['dirty'] = True
    ev = Evidence(repo, store.root / job_id, job, {})
    assert not ev.file(str(target.relative_to(repo)), 'locate')
    assert 'Historical dirty' in ev.items[0]['reason']


def test_xml_structure_and_sensitive_values_are_sanitized(tmp_path):
    repo, target = repository(tmp_path)
    xml = tmp_path / 'page.xml'
    xml.write_text('<hierarchy><node resource-id="password" text="private-value" password="true"/><node text="13812345678"/><node text="影集" selected="true" bounds="[0,1][2,3]"/></hierarchy>')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'android', {'XML': xml})
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    assert ev.artifact('XML')
    content = ev.items[0]['content']
    assert 'private-value' not in content and '13812345678' not in content
    rows = json.loads(content)
    assert rows[3]['attributes']['text'] == '影集'
    assert rows[3]['parent'] == 0 and rows[3]['attributes']['bounds'] == '[0,1][2,3]'


def test_reviewed_image_is_actual_input_and_changed_image_is_unavailable(tmp_path):
    repo, target = repository(tmp_path)
    png = tmp_path / 'page.png'
    Image.new('RGB', (10, 10), 'white').save(png)
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'android', {'PNG': png})
    store = Store(tmp_path / 'queue')
    path = store.root / job_id / 'failure.png'
    ev = Evidence(repo, path.parent, store.get(job_id), {})
    assert not ev.artifact('PNG')
    write_json(path.parent / 'reviewed-evidence.json', {'screenshots': [dict(path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), privacy_reviewed=True, related=True)]})
    ev = Evidence(repo, path.parent, store.get(job_id), {})
    assert ev.artifact('PNG') and ev.context()['reviewed_images'] == [str(path)]
    Image.new('RGB', (10, 10), 'black').save(path)
    ev = Evidence(repo, path.parent, store.get(job_id), {})
    assert not ev.artifact('PNG') and ev.images == []


def test_source_traversal_symlink_and_commands_rejected(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    outside = tmp_path / 'outside.py'
    outside.write_text('SECRET')
    link = target.parent / 'escape.py'
    link.symlink_to(outside)
    for req in [request('source_function', '../outside.py', 'read'), request('source_function', str(link.relative_to(repo)), 'read'),
                request('shell', 'cat credentials'), request('source_function', str(target.relative_to(repo)), 'locate', 'current')]:
        assert not ev.request(req)
    assert 'SECRET' not in json.dumps(ev.context())
    assert {x['status'] for x in ev.items} <= {'unavailable', 'rejected'}


def test_function_budget_marks_missing_without_partial_code(tmp_path):
    repo, target = repository(tmp_path)
    target.write_text('def giant():\n    value = "' + 'x' * 8000 + '"\n    return value\n')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'android')
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {'context_chars': 4000})
    assert not ev.file(str(target.relative_to(repo)), 'giant')
    assert ev.items[0]['status'] == 'unavailable' and 'content' not in ev.items[0]


def test_related_history_body_and_yaml_are_included(tmp_path):
    repo, target = repository(tmp_path)
    history = repo / APP / 'docs/test-fixes'
    history.mkdir(parents=True)
    (history / 'README.md').write_text('| Android photo album | [photo](android-photo-album.md) | missing album |')
    (history / 'android-photo-album.md').write_text('Historical picker only exposes fixed categories.')
    test = repo / APP / 'tests/message/test_publish_note.py'
    test.parent.mkdir(parents=True)
    test.write_text('def test_publish():\n    return "testdata/publish_notes.yaml"\n')
    data = test.parent / 'testdata/publish_notes.yaml'
    data.parent.mkdir()
    data.write_text('album: 长白山\n')
    job_id = enqueue_failure(repo, tmp_path / 'queue', str(test.relative_to(repo)) + '::test_publish', 'call', 'Android photo album not found', 'android')
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    items = ev.initial()['evidence']
    assert any('Historical picker' in x.get('content', '') for x in items)
    assert any('album: 长白山' in x.get('content', '') for x in items)


def test_nonblocking_uncertainty_routes_to_repair_and_legacy_string_does_not(tmp_path, monkeypatch):
    repo, target, store, job_id, ev = fixture(tmp_path)
    result = v2(uncertainties=[dict(question='App version missing', blocking=False, affects='Not needed for locator mismatch')])
    validate_decision(result)
    assert not has_blockers(result)
    assert has_blockers(decision(uncertainties=['old unclassified doubt']))
    worker = Worker(repo, store.root, {}, Agent([result]))
    called = []
    monkeypatch.setattr(worker, 'repair', lambda *args: called.append(args))
    worker.process(job_id)
    assert len(called) == 1


def test_controlled_evidence_round_then_diagnosis(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    responses = [v2(decision='request_evidence', evidence_requests=[request('source_function', str(target.relative_to(repo)), 'verify')]),
                 v2(category='environment', decision='manual', recommendations=['Use a picker exposing the target album'])]
    agent = Agent(responses)
    worker = Worker(repo, store.root, {}, agent)
    result = worker.process(job_id)
    assert agent.operations == ['diagnose', 'diagnose']
    assert result['result']['evidence_rounds'] == 1
    manifests = list((store.root / job_id).glob('diagnosis-*/context.json'))
    assert len(manifests) == 2
    assert any('return "old"' in item.get('content', '') for p in manifests for item in json.loads(p.read_text())['evidence'])
    assert result['result']['diagnosis']['recommendations']


def test_repeated_request_stops_without_unbounded_calls(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    response = v2(decision='request_evidence', evidence_requests=[request('source_function', str(target.relative_to(repo)), 'verify')])
    agent = Agent([response, response])
    result = Worker(repo, store.root, {'max_evidence_rounds': 4}, agent).process(job_id)
    assert len(agent.operations) == 2
    assert result['state'] == 'needs_human'
    assert 'no new content' in result['result']['evidence_stop']


def test_zero_evidence_budget_and_legacy_decision_compatibility(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    validate_decision(decision())
    agent = Agent([v2(decision='request_evidence', evidence_requests=[request('failure_xml')])])
    result = Worker(repo, store.root, {'max_evidence_rounds': 0}, agent).process(job_id)
    assert result['result']['evidence_stop'] == 'Evidence round budget exhausted'
    assert len(agent.operations) == 1
    with pytest.raises(ValueError):
        validate_decision(v2(uncertainties=[dict(question='untyped', blocking='false', affects='repair')]))


def test_diagnose_only_cannot_repair_or_submit_bug(tmp_path, monkeypatch):
    repo, target, store, job_id, ev = fixture(tmp_path)
    worker = Worker(repo, store.root, {}, Agent([v2()]))
    monkeypatch.setattr(worker, 'repair', lambda *a: pytest.fail('repair must not execute'))
    monkeypatch.setattr(worker, 'bug', lambda *a: pytest.fail('bug must not execute'))
    result = worker.process(job_id, diagnose_only=True)
    assert result['state'] == 'diagnosed'
    assert 'no repair' in result['result']['reason']


def test_large_xml_retains_late_selected_target_and_reports_omission(tmp_path):
    repo, target = repository(tmp_path)
    xml = tmp_path / 'large.xml'
    xml.write_text('<root>' + ''.join('<node text="unrelated item %d" bounds="[0,0][1,1]"/>' % i for i in range(900)) +
                   '<node text="影集" selected="true" bounds="[0,0][1,1]"/></root>')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'android', {'XML': xml})
    store = Store(tmp_path / 'queue')
    ev = Evidence(repo, store.root / job_id, store.get(job_id), {})
    ev.artifact('XML')
    item = ev.items[0]
    assert item['status'] == 'obtained' and item['omitted_nodes'] > 0
    rows = json.loads(item['content'])
    assert any(r['attributes'].get('text') == '影集' for r in rows)
    present = {r['node'] for r in rows}
    assert all(r['parent'] is None or r['parent'] in present for r in rows)


def test_invalid_xml_and_cross_job_artifact_are_not_read(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    outside = tmp_path / 'other-job.xml'
    outside.write_text('<root text="must-not-read"/>')
    ev.payload['artifacts']['XML'] = str(outside)
    assert not ev.artifact('XML')
    assert 'must-not-read' not in json.dumps(ev.context())
    local = store.root / job_id / 'failure.xml'
    local.write_text('<!DOCTYPE root><root/>')
    ev = Evidence(repo, local.parent, store.get(job_id), {})
    ev.payload['artifacts']['XML'] = str(local)
    assert not ev.artifact('XML')
    assert 'declarations rejected' in ev.items[0]['reason']


def test_rediagnosis_clears_previous_budget_stop(tmp_path):
    repo, target, store, job_id, ev = fixture(tmp_path)
    store.update(job_id, 'needs_human', evidence_stop='Evidence round budget exhausted')
    worker = Worker(repo, store.root, {}, Agent([v2(category='environment', decision='manual')]))
    result = worker.process(job_id, resume=True, rediagnose=True, diagnose_only=True)
    assert result['result']['evidence_stop'] == ''
    assert 'budget exhausted' not in result['result']['reason']
