from __future__ import annotations

import ast
from collections import Counter
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

from .agent import run_bounded
from .store import APP, git, redact, write_json


def prepare_worktree(repo, store, job):
    payload, previous = job['payload'], job['result']
    if payload['dirty']:
        raise ValueError('Failure ran with uncommitted files; exact source snapshot needs human review')
    branch = 'codex/test-fix/' + job['fingerprint']
    worktree = store.root / 'worktrees' / job['fingerprint']
    if previous.get('worktree'):
        if Path(previous['worktree']).resolve() != worktree or git(worktree, 'branch', '--show-current') != branch:
            raise ValueError('Worktree identity mismatch')
        return worktree, branch
    # Same issue at same source uses its existing isolated branch; never reset it.
    if worktree.exists():
        if git(worktree, 'branch', '--show-current') != branch or git(worktree, 'rev-parse', 'HEAD') != payload['commit']:
            raise ValueError('Existing issue worktree does not match failure revision')
    else:
        git(repo, 'worktree', 'add', '-b', branch, str(worktree), payload['commit'])
    store.update(job['id'], 'repairing', worktree=str(worktree), branch=branch)
    return worktree, branch


def check_patch(worktree, patch, max_lines=200):
    if not patch.strip() or len(patch.splitlines()) > max_lines:
        raise ValueError('Empty or oversized patch')
    if re.search(r'(?m)^(?:new file mode|deleted file mode|old mode|new mode|rename |copy |GIT binary patch)', patch):
        raise ValueError('File deletion, rename, mode or binary changes require human review')
    paths = re.findall(r'^\+\+\+ b/(.+)$', patch, re.M)
    old_paths = re.findall(r'^--- a/(.+)$', patch, re.M)
    headers = re.findall(r'^diff --git a/(.+) b/(.+)$', patch, re.M)
    if old_paths != paths or headers != [(p, p) for p in paths]:
        raise ValueError('Only same-path edits of existing files are supported')
    if not paths:
        raise ValueError('Expected a unified git diff')
    for name in paths:
        path = PurePosixPath(name)
        allowed = (name.startswith(APP + '/velowind_appium/modules/') or
                   name.startswith(APP + '/tests/unit-test/'))
        if not allowed or '..' in path.parts or not name.endswith('.py'):
            raise ValueError('Patch outside allowed automation modules/unit tests: ' + name)
        target = worktree / name
        if target.is_symlink() or not target.resolve().is_relative_to(worktree.resolve()):
            raise ValueError('Unsafe patch target')
    # Reject common bypasses and altered waits/thresholds for human review.
    changed = '\n'.join(line for line in patch.splitlines()
                        if line[:1] in {'+', '-'} and not line.startswith(('+++', '---')))
    if re.search(r'\b(skip|skipif|xfail|sleep|timeout|threshold|tolerance|waitForIdleTimeout)\b|except\b', changed):
        raise ValueError('Bypass, exception handling, wait or threshold changes need human review')
    subprocess.run(['git', '-C', str(worktree), 'apply', '--check', '-'], input=patch,
                   text=True, capture_output=True, check=True)
    return paths


def signatures(source):
    tree = ast.parse(source)
    assertions = Counter(ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                         if isinstance(node, ast.Assert))
    tests = {ast.dump(node, include_attributes=False) for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')}
    return assertions, tests


def apply_patch(worktree, patch, paths):
    before = {p: signatures((worktree / p).read_text()) if (worktree / p).exists()
              else (Counter(), set()) for p in paths}
    subprocess.run(['git', '-C', str(worktree), 'apply', '-'], input=patch,
                   text=True, capture_output=True, check=True)
    try:
        for path, (assertions, tests) in before.items():
            after_assertions, after_tests = signatures((worktree / path).read_text())
            if assertions - after_assertions or not tests.issubset(after_tests):
                raise ValueError('Patch removed/changed an assertion or removed a test')
    except Exception:
        # Revert only this attempt, preserve earlier failures and patches on disk.
        subprocess.run(['git', '-C', str(worktree), 'apply', '-R', '-'], input=patch,
                       text=True, capture_output=True, check=True)
        raise


def run_tests(worktree, selectors, directory, timeout, *, device=False, platform='ios', repo=None):
    if not selectors or not all(isinstance(x, str) and x.startswith(APP + '/tests/') and
                                '..' not in PurePosixPath(x.split('::')[0]).parts for x in selectors):
        raise ValueError('Validation needs explicit repository test selectors')
    if not device and any('/tests/unit-test/' not in x for x in selectors):
        raise ValueError('Unit validation must only select unit tests')
    directory.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(worktree / APP), VW_APPIUM_TRIAGE_ENABLED='false',
               VW_APPIUM_PLATFORM=platform, VW_APPIUM_AUTO_OPEN_REPORT='false',
               VW_APPIUM_DEVICE_LOCK_DIR=str(Path(repo or worktree) / '.tmp/appium-triage'),
               VW_APPIUM_RUN_ID=directory.name, VW_APPIUM_ARTIFACT_DIR=str(directory / 'artifacts'),
               VW_ALLURE_RESULTS_DIR=str(directory / 'allure-results'),
               VW_APPIUM_TIMING_DIR=str(directory / 'timing'))
    python = str(Path(repo or worktree) / '.venv/bin/python')
    if not Path(python).exists():
        python = sys.executable
    code, out, err = run_bounded([python, '-m', 'pytest', '-q', '-ra',
                                 '--junitxml=' + str(directory / 'junit.xml'),
                                 '--alluredir=' + str(directory / 'allure-results'), *selectors],
                                cwd=worktree, timeout=timeout, env=env)
    (directory / 'pytest.log').write_text(redact(out + '\n' + err))
    # Exit zero with skips/xfails or no cases is not accepted as verified.
    import xml.etree.ElementTree as ET
    suites = list(ET.parse(directory / 'junit.xml').getroot().iter('testsuite'))
    passed = code == 0 and bool(suites) and sum(int(s.get('tests', '0')) for s in suites) > 0
    passed = passed and not any(int(s.get(k, '0')) for s in suites for k in ('failures', 'errors', 'skipped'))
    return {'passed': passed, 'exit_code': code, 'report': str(directory), 'selectors': selectors}


def device_busy():
    # A running Appium server is normal; another runner owns its session.
    result = subprocess.run(['ps', '-axo', 'pid=,args='], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if re.search(r'(?:^|[ /])(?:pytest|run_ios_tests|run_android_tests)(?:[ .]|$)', line):
            return True
    return False


def cleanup_status(directory):
    states = []
    for path in (directory / 'allure-results').glob('*-result.json'):
        import json
        def walk(item):
            for attachment in item.get('attachments', []):
                name = attachment.get('name', '')
                if 'cleanup-pending' in name:
                    states.append('pending')
                elif 'cleanup-result' in name:
                    states.append('recorded_needs_review')
            for step in item.get('steps', []):
                walk(step)
        walk(json.loads(path.read_text()))
    return 'pending' if 'pending' in states else ('recorded_needs_review' if states else 'unknown')
