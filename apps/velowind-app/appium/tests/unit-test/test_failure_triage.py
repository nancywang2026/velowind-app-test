import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from velowind_appium.triage.agent import validate_decision
from velowind_appium.triage.store import APP, Store, enqueue_failure, git, redact
from velowind_appium.triage.repair import apply_patch, check_patch, prepare_worktree
from velowind_appium.triage.worker import Worker


def repository(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init')
    git(repo, 'config', 'user.name', 'Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    target = repo / APP / 'velowind_appium/modules/sample.py'
    target.parent.mkdir(parents=True)
    target.write_text('def locate():\n    return "old"\n\ndef verify():\n    assert locate() == "new"\n')
    unit = repo / APP / 'tests/unit-test/test_sample.py'
    unit.parent.mkdir(parents=True)
    unit.write_text('def test_expected():\n    from velowind_appium.modules.sample import locate\n    assert locate() == "new"\n')
    (repo / APP / 'velowind_appium/__init__.py').write_text('')
    (target.parent / '__init__.py').write_text('')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'fixture')
    return repo, target


def decision(category='automation_defect', **changes):
    result = dict(category=category, summary='Old locator', evidence=['Source and current screen disagree'],
                  uncertainties=[], expected='new', actual='old', steps=['Open sample'],
                  patch='', assertions_preserved=True, decision='propose')
    result.update(changes)
    return result


class Agent:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.operations = []

    def ask(self, operation, context):
        self.operations.append(operation)
        return next(self.responses)


def enqueue(repo, tmp_path):
    return enqueue_failure(repo, tmp_path / 'queue', APP + '/tests/unit-test/test_sample.py::test_expected',
                           'call', 'AssertionError: old != new', 'ios')


def patch_for(repo, target):
    target.write_text(target.read_text().replace('return "old"', 'return "new"'))
    patch = git(repo, 'diff') + '\n'
    git(repo, 'restore', '.')
    return patch


def test_redaction_hides_auth_contact_values():
    text = redact('password="supersecret" token: abc Bearer eyJ.abc 13812345678 test@example.com')
    for secret in ['supersecret', 'eyJ.abc', '13812345678', 'test@example.com']:
        assert secret not in text


def test_capture_keeps_occurrences_and_exact_revision(tmp_path):
    repo, target = repository(tmp_path)
    first = enqueue(repo, tmp_path)
    second = enqueue(repo, tmp_path)
    store = Store(tmp_path / 'queue')
    assert first != second
    assert store.get(first)['fingerprint'] == store.get(second)['fingerprint']
    target.write_text('changed')
    dirty = enqueue(repo, tmp_path)
    assert store.get(dirty)['payload']['dirty'] is True
    with pytest.raises(ValueError, match='uncommitted'):
        prepare_worktree(repo, store, store.get(dirty))


def test_worktree_is_new_branch_and_preserves_original(tmp_path):
    repo, target = repository(tmp_path)
    original = git(repo, 'branch', '--show-current')
    job_id = enqueue(repo, tmp_path)
    store = Store(tmp_path / 'queue')
    worktree, branch = prepare_worktree(repo, store, store.get(job_id))
    assert branch.startswith('codex/test-fix/')
    assert git(repo, 'branch', '--show-current') == original
    assert git(worktree, 'branch', '--show-current') == branch
    assert prepare_worktree(repo, store, store.get(job_id)) == (worktree, branch)


def test_guard_rejects_business_changes_and_assertion_weakening(tmp_path):
    repo, target = repository(tmp_path)
    patch = patch_for(repo, target)
    assert check_patch(repo, patch)
    for bad in [patch.replace('/velowind_appium/modules/', '/business/'),
                patch.replace('return "new"', 'pytest.skip("unavailable")'),
                patch.replace('return "new"', 'sleep(30)')]:
        with pytest.raises(ValueError):
            check_patch(repo, bad)
    target.write_text(target.read_text().replace('assert locate() == "new"', 'assert True'))
    bad = git(repo, 'diff') + '\n'
    git(repo, 'restore', '.')
    paths = check_patch(repo, bad)
    with pytest.raises(ValueError, match='assertion'):
        apply_patch(repo, bad, paths)
    assert git(repo, 'diff') == ''


def test_schema_and_uncertainty_block_mutations(tmp_path):
    with pytest.raises(ValueError):
        validate_decision({'category': 'product_defect'})
    repo, target = repository(tmp_path)
    job_id = enqueue(repo, tmp_path)
    agent = Agent([decision(uncertainties=['Requirement unclear'])])
    worker = Worker(repo, tmp_path / 'queue', {}, agent)
    result = worker.process(job_id)
    assert result['state'] == 'needs_human'
    assert agent.operations == ['diagnose']
    assert not (tmp_path / 'queue/worktrees').exists()


def test_full_repair_runs_actual_unit_tests_on_isolated_branch(tmp_path):
    repo, target = repository(tmp_path)
    patch = patch_for(repo, target)
    job_id = enqueue(repo, tmp_path)
    nodeid = Store(tmp_path / 'queue').get(job_id)['payload']['nodeid']
    agent = Agent([decision(), decision(patch=patch), decision(decision='accept')])
    config = {'validation': {nodeid: {'unit': [nodeid], 'device': [nodeid], 'safe_to_rerun': False}}}
    result = Worker(repo, tmp_path / 'queue', config, agent).process(job_id)
    assert result['result']['unit']['passed'], result
    assert result['state'] == 'needs_human'
    assert result['result']['device_validation'] == 'not_run'
    assert 'return "old"' in target.read_text()
    assert 'return "new"' in (Path(result['result']['worktree']) / target.relative_to(repo)).read_text()
    assert git(repo, 'log', '--format=%s') == 'fixture'


def test_product_bug_requires_reviewed_evidence(tmp_path):
    repo, _ = repository(tmp_path)
    job_id = enqueue(repo, tmp_path)
    worker = Worker(repo, tmp_path / 'queue', {}, Agent([decision('product_defect')]))
    result = worker.process(job_id)
    assert result['state'] == 'waiting_evidence'
    assert (tmp_path / 'queue' / job_id / 'bug-draft.json').exists()
    # No polling or repeated AI calls for a missing evidence review.
    worker.tick()
    assert worker.store.get(job_id)['state'] == 'waiting_evidence'


def test_worker_lock_is_exclusive_and_released(tmp_path):
    first, second = Store(tmp_path), Store(tmp_path)
    with first.lock():
        with pytest.raises(RuntimeError, match='Another'):
            with second.lock():
                pass
    with second.lock():
        pass


def test_pytest_plugin_captures_setup_call_teardown_without_device(tmp_path):
    # Prove real pytest hook behavior without repository device fixtures.
    repo, _ = repository(tmp_path)
    source = tmp_path / 'test_synthetic.py'
    source.write_text('''import pytest
@pytest.fixture
def setup_fail(): raise RuntimeError("setup")
@pytest.fixture
def teardown_fail():
    yield
    raise RuntimeError("teardown")
def test_setup(setup_fail): pass
def test_teardown(teardown_fail): pass
def test_call(): assert False
def test_pass(): pass
''')
    package = str(Path(__file__).resolve().parents[2])
    env = dict(os.environ, PYTHONPATH=package, VW_APPIUM_TRIAGE_DIR=str(tmp_path / 'queue'), VW_APPIUM_TRIAGE_ENABLED='true', VW_APPIUM_TRIAGE_AUTOSTART='false')
    result = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'velowind_appium.pytest_failure_triage', '-q', str(source)],
                            cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    store = Store(tmp_path / 'queue')
    assert len(store.list()) == 3
    assert {store.get(x['id'])['payload']['phase'] for x in store.list()} == {'setup', 'call', 'teardown'}


def test_evidence_snapshot_survives_original_overwrite(tmp_path):
    repo, _ = repository(tmp_path)
    screenshot = tmp_path / 'original.png'
    screenshot.write_bytes(b'original frame')
    xml = tmp_path / 'original.xml'
    xml.write_text('<node password="secret"/>')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'ios',
                             {'PNG': screenshot, 'XML': xml})
    screenshot.write_bytes(b'next frame')
    payload = Store(tmp_path / 'queue').get(job_id)['payload']
    assert Path(payload['artifacts']['PNG']).read_bytes() == b'original frame'
    assert 'secret' not in Path(payload['artifacts']['XML']).read_text()


def test_taiga_resume_deduplicates_issue_and_partial_attachment_upload(tmp_path, monkeypatch):
    from velowind_appium.triage.taiga import Taiga
    monkeypatch.setenv('VW_TRIAGE_TAIGA_TOKEN', 'synthetic-token')
    client = Taiga({'api_url': 'http://localhost/api/v1', 'project_id': 1})
    issues, attachments, calls = [], [], []
    failed = [False]
    def request(method, path, data=None, content_type=None):
        calls.append((method, path))
        if method == 'GET' and path.startswith('issues?'):
            return issues if 'page=1&' in path else []
        if method == 'GET' and path.startswith('issues/attachments?'):
            return attachments if 'page=1&' in path else []
        if method == 'GET':
            return issues[0]
        if path == 'issues':
            issues.append(dict(data, id=10, ref=20, version=1))
            return issues[0]
        if path == 'issues/attachments':
            if not failed[0]:
                failed[0] = True
                raise OSError('network interrupted')
            import re
            marker = re.search(b'name="description"\r\n\r\n([^\r]+)', data).group(1).decode()
            result = {'id': 7, 'description': marker}
            attachments.append(result)
            return result
        raise AssertionError((method, path))
    monkeypatch.setattr(client, 'request', request)
    path = tmp_path / 'screen.png'
    path.write_bytes(b'synthetic png')
    job = {'id': 'run1', 'fingerprint': 'signature'}
    draft = {'subject': 'Failure', 'description': 'Expected/actual evidence'}
    with pytest.raises(OSError):
        client.submit(job, draft, [path])
    assert client.submit(job, draft, [path])['id'] == 10
    client.submit(job, draft, [path])
    assert len(issues) == len(attachments) == 1
    assert sum(method == 'POST' and path == 'issues' for method, path in calls) == 1


def test_same_issue_occurrence_does_not_reapply_existing_patch(tmp_path):
    repo, target = repository(tmp_path)
    first = enqueue(repo, tmp_path)
    store = Store(tmp_path / 'queue')
    worktree, branch = prepare_worktree(repo, store, store.get(first))
    second = enqueue(repo, tmp_path)
    worker = Worker(repo, tmp_path / 'queue', {}, Agent([decision()]))
    result = worker.process(second)
    assert result['state'] == 'needs_human'
    assert result['result']['related_job'] == first
    assert result['result']['branch'] == branch


def test_bounded_command_kills_only_its_own_child_group(tmp_path):
    from velowind_appium.triage.agent import run_bounded
    with pytest.raises(RuntimeError, match='time budget'):
        run_bounded([sys.executable, '-c', 'import time; time.sleep(20)'], cwd=tmp_path, timeout=0.05)


def test_codex_adapter_enforces_readonly_and_schema_without_live_model(tmp_path, monkeypatch):
    monkeypatch.setenv("VW_TRIAGE_TAIGA_TOKEN", "must-not-reach-agent")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-override-login")
    monkeypatch.setenv("CODEX_API_KEY", "must-not-override-login")
    from velowind_appium.triage.agent import CodexAgent
    skill = tmp_path / 'SKILL.md'
    skill.write_text('Do not invoke tools.')
    binary = tmp_path / 'fake-codex'
    binary.write_text('#!' + sys.executable + '\n' + '''import sys, json, os
from pathlib import Path
assert 'VW_TRIAGE_TAIGA_TOKEN' not in os.environ
assert 'OPENAI_API_KEY' not in os.environ
assert 'CODEX_API_KEY' not in os.environ
assert '--ignore-user-config' in sys.argv
assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'
assert '--output-schema' in sys.argv
assert 'Operation: diagnose' in sys.stdin.read()
Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(''' + repr(decision()) + '''))
''')
    binary.chmod(0o700)
    assert CodexAgent(skill, binary=str(binary)).ask('diagnose', {})['category'] == 'automation_defect'


def test_existing_test_cannot_be_made_to_return_before_assertion(tmp_path):
    repo, target = repository(tmp_path)
    unit = repo / APP / 'tests/unit-test/test_sample.py'
    unit.write_text(unit.read_text().replace('    from ', '    return\n    from '))
    patch = git(repo, 'diff') + '\n'
    git(repo, 'restore', '.')
    paths = check_patch(repo, patch)
    with pytest.raises(ValueError):
        apply_patch(repo, patch, paths)
    assert git(repo, 'diff') == ''


def test_taiga_http_client_honors_last_page_header(tmp_path, monkeypatch):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    from velowind_appium.triage.taiga import Taiga
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            assert self.headers['Authorization'] == 'Bearer synthetic-token'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-Pagination-Next', '')
            self.end_headers()
            self.wfile.write(b'[{"id":1}]')
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('VW_TRIAGE_TAIGA_TOKEN', 'synthetic-token')
    try:
        client = Taiga({'api_url': 'http://127.0.0.1:' + str(server.server_port), 'project_id': 1})
        assert client.list('issues', {'project': 1}) == [{'id': 1}]
        assert len(requests) == 1
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_source_revision_drift_cannot_be_repaired_from_new_head(tmp_path):
    repo, target = repository(tmp_path)
    original = git(repo, 'rev-parse', 'HEAD')
    target.write_text(target.read_text().replace('return "old"', 'return "other"'))
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'changed while test ran')
    job_id = enqueue_failure(repo, tmp_path / 'queue', 'test_sample', 'call', 'failed', 'ios',
                             source_snapshot={'commit': original, 'dirty': False, 'dirty_hash': None})
    store = Store(tmp_path / 'queue')
    payload = store.get(job_id)['payload']
    assert payload['commit'] == original
    assert payload['source_changed_during_run'] is True
    assert payload['dirty'] is True
    with pytest.raises(ValueError):
        prepare_worktree(repo, store, store.get(job_id))


def test_failed_repairs_stop_at_two_and_keep_both_reports(tmp_path):
    repo, target = repository(tmp_path)
    patch = patch_for(repo, target).replace('+    return "new"', '+    return "wrong"')
    job_id = enqueue(repo, tmp_path)
    store = Store(tmp_path / 'queue')
    nodeid = store.get(job_id)['payload']['nodeid']
    agent = Agent([decision(), decision(patch=patch), decision(decision='accept'),
                   decision(patch=patch), decision(decision='accept')])
    worker = Worker(repo, tmp_path / 'queue', {'validation': {nodeid: {'unit': [nodeid]}}}, agent)
    result = worker.process(job_id)
    assert result['state'] == 'needs_human'
    assert result['result']['attempts'] == 2
    for attempt in ['attempt-1', 'attempt-2']:
        assert (tmp_path / 'queue' / job_id / attempt / 'proposal.patch').exists()
        assert (tmp_path / 'queue' / job_id / attempt / 'unit/pytest.log').exists()
    worktree_file = Path(result['result']['worktree']) / target.relative_to(repo)
    assert 'return "old"' in worktree_file.read_text()
    assert agent.operations == ['diagnose', 'repair', 'review', 'repair', 'review']


def test_taiga_project_slug_is_resolved_with_authenticated_lookup(monkeypatch):
    from velowind_appium.triage.taiga import Taiga
    monkeypatch.setenv('VW_TRIAGE_TAIGA_TOKEN', 'synthetic-token')
    seen = []
    def lookup(self, method, path, data=None, content_type=None):
        seen.append((method, path, self.token))
        return {'id': 42, 'slug': 'velowind-app'}
    monkeypatch.setattr(Taiga, 'request', lookup)
    client = Taiga({'api_url': 'https://project.velowind.com/taiga/api/v1', 'project_slug': 'velowind-app'})
    assert client.project == 42
    assert seen == [('GET', 'projects/by_slug?slug=velowind-app', 'synthetic-token')]


def test_taiga_project_slug_mismatch_stops_submission(monkeypatch):
    from velowind_appium.triage.taiga import Taiga
    monkeypatch.setenv('VW_TRIAGE_TAIGA_TOKEN', 'synthetic-token')
    monkeypatch.setattr(Taiga, 'request', lambda *args: {'id': 42, 'slug': 'another-project'})
    with pytest.raises(ValueError, match='did not match'):
        Taiga({'api_url': 'https://project.velowind.com/taiga/api/v1', 'project_slug': 'velowind-app'})


def test_recovery_keeps_previous_failure_history(tmp_path):
    repo, _ = repository(tmp_path)
    job_id = enqueue(repo, tmp_path)
    store = Store(tmp_path / 'queue')
    store.update(job_id, 'needs_human', reason='first attempt authentication failure')
    store.update(job_id, 'running', reason='explicit retry')
    store.update(job_id, 'needs_human', reason='intentional probe correctly classified')
    events = store.history(job_id)
    assert [entry['state'] for entry in events] == ['queued', 'needs_human', 'running', 'needs_human']
    assert events[1]['result']['reason'] == 'first attempt authentication failure'


def test_codex_failure_message_is_actionable_and_redacts_credentials(tmp_path):
    from velowind_appium.triage.agent import CodexAgent
    skill = tmp_path / 'SKILL.md'
    skill.write_text('Do not invoke tools.')
    binary = tmp_path / 'failing-codex'
    binary.write_text('#!' + sys.executable + '\nimport sys\nsys.stderr.write("401 Unauthorized password=private sk-example****************masked")\nsys.exit(3)\n')
    binary.chmod(0o700)
    with pytest.raises(RuntimeError, match='exit 3') as caught:
        CodexAgent(skill, binary=str(binary)).ask('diagnose', {})
    assert '401 Unauthorized' in str(caught.value)
    assert 'private' not in str(caught.value)
    assert 'sk-example' not in str(caught.value)
