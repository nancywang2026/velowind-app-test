"""Export recorded message checks without executing requests or device operations.

Historical records without wall-clock timestamps keep that absence. Their measured
monotonic durations are shown as parameters, never reconstructed as execution times.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from .case_descriptions import description, render_description


STATUS = {'passed': 'passed', 'failed': 'failed', 'blocked': 'skipped'}


def export_record(record: dict, source: Path, results: Path) -> int:
    results.mkdir(parents=True, exist_ok=True)
    count = 0
    for index, row in enumerate(record.get('cases', [])):
        if row['status'] == 'running':
            continue
        status = STATUS[row['status']]  # Unknown states must never become passes.
        name = row['name']
        key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source.resolve()}:{record.get('run_id', '')}:{index}:{name}"))
        attachments = []

        def attach(label, content, suffix, mime):
            filename = f'{key}-{len(attachments)}-attachment.{suffix}'
            (results / filename).write_bytes(content)
            attachments.append({'name': label, 'source': filename, 'type': mime})

        evidence = {k: row[k] for k in ('name', 'status', 'verification', 'seconds', 'error',
                    'reason', 'http_status', 'business_code', 'message_key', 'start', 'stop',
                    'image_display_checks', 'screenshot_error') if k in row}
        # Do not copy login responses, account files, or arbitrary input fields.
        evidence['resources'] = [{k: item[k] for k in ('kind', 'id', 'status', 'reason', 'residual', 'error', 'sha256')
                                  if k in item} for item in record.get('resources', [])]
        attach('原始断言结果与资源保留状态', json.dumps(evidence, ensure_ascii=False, indent=2).encode(), 'json', 'application/json')
        for xml in sorted(source.parent.glob('*.xml')):
            attach('本组XML快照（非逐步骤）：' + xml.name, xml.read_bytes(), 'xml', 'application/xml')
        for screenshot in row.get('screenshots', []):
            path = (source.parent / screenshot['path']).resolve()
            if path.parent != source.parent.resolve():
                raise ValueError('Screenshot must be inside this suite directory')
            content = path.read_bytes()
            if not content.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid PNG screenshot')
            attach(screenshot['name'], content, 'png', 'image/png')
        spec = row.get('test_description') or description(name)
        details = render_description(spec) if spec else '测试内容及验证点描述尚未配置：' + name
        screenshot_note = ('已附本用例执行结束时的真实截图。' if row.get('screenshots')
                           else '本次原始执行记录无用例截图，不以后补画面代替。')
        if row.get('screenshot_error'):
            screenshot_note += ' 截图采集失败：' + row['screenshot_error']
        result = {
            'uuid': key, 'historyId': hashlib.sha256(name.encode()).hexdigest(),
            'testCaseId': hashlib.sha256(name.encode()).hexdigest(),
            'name': spec['title'] if spec else name, 'fullName': 'message_regression.' + name,
            'status': status, 'stage': 'finished',
            'description': details + '\n\n**截图证据**\n' + screenshot_note + '\n\n执行记录：' + str(source) + '。'
                '报告导出不会执行测试。XML附件为同组现场快照，不作为逐步骤截图。缺失的历史绝对起止时间不补造。',
            'labels': [{'name': 'parentSuite', 'value': '消息自动化'},
                       {'name': 'suite', 'value': source.parent.name},
                       {'name': 'feature', 'value': name.split('.')[0]},
                       {'name': 'framework', 'value': 'message live runner'}],
            'parameters': [{'name': 'verification', 'value': str(row.get('verification', 'unspecified'))},
                           {'name': 'recorded duration (seconds)', 'value': str(row.get('seconds', 'unavailable'))}],
            'attachments': attachments,
        }
        if 'start' in row and 'stop' in row:
            result.update(start=row['start'], stop=row['stop'])
        if status != 'passed':
            result['statusDetails'] = {'message': row.get('reason') or row.get('error') or row['status'],
                                       'trace': row.get('error', '')}
        target = results / f'{key}-result.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        temporary.replace(target)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='One live-results.json or a run directory')
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='Generate HTML with the installed Allure CLI')
    args = parser.parse_args()
    sources = [args.input] if args.input.is_file() else sorted(args.input.glob('*/live-results.json'))
    if not sources:
        parser.error('No recorded results found')
    count = sum(export_record(json.loads(source.read_text()), source, args.results) for source in sources)
    print(f'Exported {count} recorded checks to {args.results}')
    if args.report:
        allure = shutil.which('allure')
        if not allure:
            parser.error('Allure CLI unavailable; raw results have been preserved')
        subprocess.run([allure, 'generate', str(args.results), '--clean', '-o', str(args.report)], check=True)


if __name__ == '__main__':
    main()
