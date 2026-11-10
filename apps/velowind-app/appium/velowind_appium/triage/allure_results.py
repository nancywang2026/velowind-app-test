"""Link asynchronous diagnoses to exact Allure results without changing test outcomes."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from .agent import run_bounded
from .store import APP, redact, write_json


COMPLETE_MARKER = '.triage-run-complete.json'


def import_failures(store, results, report=None):
    results = Path(results).resolve()
    if not results.is_dir():
        raise ValueError('Allure results directory does not exist')
    report = Path(report).resolve() if report else results.parent / 'allure-report'
    known = {x['payload'].get('metadata', {}).get('allure_uuid') for x in
             (store.get(row['id']) for row in store.list())}
    timing = []
    commit = 'unknown'
    for path in (results.parent / 'timing').glob('*/timings.json'):
        data = json.loads(path.read_text())
        commit = data.get('git_commit', 'unknown')
        timing.extend(data.get('cases', []))
    imported = []
    for path in sorted(results.glob('*-result.json')):
        data = json.loads(path.read_text())
        if data.get('status') not in {'failed', 'broken'}:
            continue
        labels = [x.get('value') for x in data.get('labels', []) if x.get('name') == 'triageJobId']
        if data.get('uuid') in known or any(x['id'] in labels for x in store.list()):
            continue
        if not data.get('uuid'):
            raise ValueError('Allure failure has no stable UUID')
        matches = [x for x in timing if x.get('name') == data.get('name') or
                   x.get('nodeid', '').split('::')[-1] == data.get('name')]
        if len(matches) == 1:
            nodeid = matches[0]['nodeid']
            if nodeid.startswith('tests/'):
                nodeid = APP + '/' + nodeid
        else:
            module, separator, function = data.get('fullName', '').partition('#')
            if not separator or not module.startswith('tests.'):
                raise ValueError('Cannot establish a repository selector from Allure result')
            suffix = data.get('name', '')[len(function):] if data.get('name', '').startswith(function) else ''
            nodeid = APP + '/' + module.replace('.', '/') + '.py::' + function + suffix
        artifacts = {}
        for attachment in data.get('attachments', []):
            source = (results / attachment.get('source', '')).resolve()
            if not source.is_relative_to(results) or not source.is_file():
                continue
            kind = {'.png': 'PNG', '.xml': 'XML'}.get(source.suffix.lower())
            if kind:
                artifacts[kind] = str(source)
        metadata = {'run_id': results.parent.name, 'allure_results_dir': str(results),
                    'allure_report_dir': str(report), 'allure_uuid': data['uuid'],
                    'allure_result_file': path.name, 'imported_from_allure': True,
                    'source_snapshot': 'Historical dirty source unavailable; do not automatically patch'}
        payload = dict(nodeid=nodeid, phase='call', error=redact(data.get('statusDetails', {}).get('message', 'Allure failed result')),
                       platform='android' if 'android' in str(results) else 'ios', commit=commit,
                       dirty=True, dirty_hash=None, artifacts=artifacts, metadata=metadata,
                       cleanup='unknown', device_validation='failed')
        job_id = store.enqueue(payload)
        known.add(data['uuid'])
        imported.append(job_id)
    return imported


def diagnosis_document(job):
    result = {k: v for k, v in job['result'].items() if not k.startswith('allure_')}
    return {'job_id': job['id'], 'state': job['state'], 'test': job['payload']['nodeid'],
            'original_assertion_result': 'unchanged', 'result': result}


def publish(store, job):
    metadata = job['payload'].get('metadata', {})
    if not metadata.get('allure_results_dir'):
        return {'status': 'unlinked'}
    results = Path(metadata['allure_results_dir']).resolve()
    if not metadata.get('imported_from_allure') and not (results / COMPLETE_MARKER).exists():
        return {'status': 'pending'}
    candidates = []
    for path in results.glob('*-result.json'):
        if metadata.get('allure_result_file') and path.name != metadata['allure_result_file']:
            continue
        data = json.loads(path.read_text())
        labels = [x.get('value') for x in data.get('labels', []) if x.get('name') == 'triageJobId']
        if (metadata.get('allure_uuid') and data.get('uuid') == metadata['allure_uuid']) or job['id'] in labels:
            candidates.append((path, data))
    if len(candidates) != 1:
        return {'status': 'pending', 'reason': 'Exact Allure result association unavailable'}
    document = diagnosis_document(job)
    document['original_allure_status'] = candidates[0][1].get('status')
    encoded = redact(json.dumps(document, ensure_ascii=False, indent=2))
    signature = hashlib.sha256(encoded.encode()).hexdigest()[:16]
    source = 'triage-' + job['id'] + '-' + signature
    path, data = candidates[0]
    if any(x.get('source') == source + '.txt' for x in data.get('attachments', [])):
        return {'status': 'unchanged', 'report': metadata.get('allure_report_dir')}
    diagnosis = job['result'].get('diagnosis') or {}
    text = '\n'.join(['AI 诊断结果', '任务: ' + job['id'], '状态: ' + job['state'],
                      '分类: ' + diagnosis.get('category', '尚未分类'),
                      '结论: ' + diagnosis.get('summary', ''),
                      '处理原因: ' + job['result'].get('reason', ''),
                      '补证轮次: ' + str(job['result'].get('evidence_rounds', 0)),
                      '补证停止原因: ' + job['result'].get('evidence_stop', ''),
                      '候选原因: ' + '；'.join(diagnosis.get('candidate_causes', [])),
                      '修改建议 / 下一步: ' + '；'.join(diagnosis.get('recommendations', [])),
                      '注意：AI 分析不改变原测试断言、清理或真机验证结果。',
                      '', '完整诊断与验证记录:', encoded])
    results.mkdir(parents=True, exist_ok=True)
    (results / (source + '.txt')).write_text(redact(text), encoding='utf-8')
    write_json(results / (source + '.json'), json.loads(encoded))
    data.setdefault('attachments', []).extend([
        {'name': 'AI 诊断结果 [' + job['state'] + ']', 'source': source + '.txt', 'type': 'text/plain'},
        {'name': 'AI 诊断结构化记录', 'source': source + '.json', 'type': 'application/json'}])
    # Preserve status, statusDetails, timing, original attachments and assertions.
    write_json(path, data)
    return {'status': 'published', 'report': metadata.get('allure_report_dir')}


def preserve_case_routes(previous, generated):
    """Keep open case URLs usable when Allure assigns new UIDs on rebuild."""
    def identity(case):
        return json.dumps([case.get('historyId'), case.get('fullName'), case.get('name'),
                           case.get('time'), case.get('parameters'), case.get('retry')], sort_keys=True)

    current = {}
    target = Path(generated) / 'data/test-cases'
    for path in target.glob('*.json'):
        case = json.loads(path.read_text())
        current.setdefault(identity(case), []).append(case)
    for path in (Path(previous) / 'data/test-cases').glob('*.json'):
        if (target / path.name).exists():
            continue
        matches = current.get(identity(json.loads(path.read_text())), [])
        if len(matches) == 1:
            alias = dict(matches[0], uid=path.stem, source=path.name)
            write_json(target / path.name, alias)


def refresh(results, report, *, timeout=120):
    results, report = Path(results).resolve(), Path(report).resolve()
    if report.parent != results.parent or report.name != 'allure-report':
        return 'custom_report_requires_manual_refresh'
    if not (report / 'index.html').is_file():
        return 'raw_results_updated_html_not_generated_yet'
    if 'Allure' not in (report / 'index.html').read_text(errors='replace'):
        raise ValueError('Refusing to replace a directory that is not an Allure report')
    binary = shutil.which('allure')
    if binary is None:
        return 'allure_cli_missing'
    target = report.parent / ('.triage-report-' + uuid.uuid4().hex)
    backup = report.parent / ('.triage-backup-' + uuid.uuid4().hex)
    try:
        code, _, stderr = run_bounded([binary, 'generate', str(results), '--clean', '-o', str(target)],
                                      cwd=results.parent, timeout=timeout)
        if code or not (target / 'index.html').is_file():
            raise RuntimeError('Allure generation failed: ' + redact(stderr[-500:]))
        preserve_case_routes(report, target)
        report.rename(backup)
        try:
            target.rename(report)
        except BaseException:
            backup.rename(report)
            raise
        shutil.rmtree(backup)
    finally:
        if target.exists():
            shutil.rmtree(target)
    return 'html_refreshed'
