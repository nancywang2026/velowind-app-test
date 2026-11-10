from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from collections import Counter
from pathlib import Path
import time

from .store import Store, QueueBusyError, write_json
from .worker import Worker


def main():
    parser = argparse.ArgumentParser(description='Appium failure triage queue and Codex worker')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument('--queue', type=Path)
    parser.add_argument('--config', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    sub.add_parser('once')
    sub.add_parser('watch')
    imported = sub.add_parser('import-allure', help='Import completed Allure failures without rerunning tests')
    imported.add_argument('results', type=Path)
    imported.add_argument('--report', type=Path)
    show = sub.add_parser('show')
    show.add_argument('job')
    review = sub.add_parser('review-evidence', help='Record a completed local screenshot/privacy review')
    review.add_argument('job')
    review.add_argument('--png', type=Path, required=True)
    review.add_argument('--device-state', choices=['disconnected', 'connected_current_captured'], required=True)
    review.add_argument('--context', type=Path, help='Locally reviewed/redacted observations or XML')
    publish = sub.add_parser('publish-allure', help='Refresh Allure attachments without another AI call')
    publish.add_argument('job')
    resume = sub.add_parser('resume')
    resume.add_argument('job')
    resume.add_argument('--rediagnose', action='store_true')
    resume.add_argument('--diagnose-only', action='store_true', help='Collect/diagnose and publish only; no repair, device or Bug submission')
    args = parser.parse_args()
    queue = args.queue or Path(os.environ.get('VW_APPIUM_TRIAGE_DIR', args.repo / '.tmp/appium-triage'))
    if args.command == 'import-allure':
        from .allure_results import import_failures
        store = Store(queue)
        jobs = import_failures(store, args.results, args.report)
        print('[triage] 已导入 ' + str(len(jobs)) + ' 个失败任务；未重跑测试。队列：' + str(store.root), flush=True)
        for job in jobs:
            print('[triage] ' + job, flush=True)
        return
    if args.command == 'review-evidence':
        import hashlib
        import shutil
        from PIL import Image
        store = Store(queue)
        store.get(args.job)
        directory = store.root / args.job
        with Image.open(args.png) as image:
            if image.format != 'PNG':
                parser.error('Reviewed screenshot must be a PNG')
            image.verify()
        target = directory / 'reviewed.png'
        if args.png.resolve() != target.resolve():
            shutil.copyfile(args.png, target)
        write_json(directory / 'reviewed-evidence.json', {
            'reviewed_at': time.time(), 'device_state': args.device_state,
            'screenshots': [{'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                             'privacy_reviewed': True, 'related': True}]})
        if args.context:
            (directory / 'reviewed-context.json').write_text(args.context.read_text())
        print('Review recorded. Use resume (with --rediagnose if adding diagnosis evidence).')
        return
    if args.command in {'list', 'show'}:
        store = Store(queue)
        result = store.list() if args.command == 'list' else dict(store.get(args.job), history=store.history(args.job))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if not args.config:
        parser.error('Worker execution requires --config (no implicit external execution)')
    config = json.loads(args.config.read_text())
    report = lambda message: print('[triage] ' + message, flush=True)
    worker = Worker(args.repo, queue, config, reporter=report)
    report('队列：' + str(worker.store.root))
    if args.command == 'publish-allure':
        with worker.store.lock():
            worker.publish_allure(args.job)
        return
    if args.command == 'resume':
        result = worker.process(args.job, resume=True, rediagnose=args.rediagnose, diagnose_only=args.diagnose_only)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    try:
        with worker.store.lock('watch') if args.command == 'watch' else nullcontext():
            if args.command == 'watch':
                report('监听已启动，每 5 秒检查；Ctrl+C 停止')
                write_json(worker.store.root / 'worker-watch.json', {'pid': os.getpid()})
            run_loop(worker, args, report)
    except KeyboardInterrupt:
        pass
    except QueueBusyError:
        report('AI worker 已运行，不重复启动监听')


def run_loop(worker, args, report):
    while True:
        if args.command == 'once':
            rows = worker.store.list()
            pending = sum(row['state'] in {'queued', 'waiting_device'} for row in rows)
            if not rows:
                report('队列为空，没有待诊断失败；本次不会调用 AI。请确认失败已入队及队列路径一致。')
            elif not pending:
                report('没有待自动处理任务。现有状态：' + json.dumps(dict(Counter(row['state'] for row in rows)), ensure_ascii=False))
                report('needs_human / waiting_evidence 等状态需查看 show JOB_ID，补充条件后显式 resume。')
            else:
                report('本次发现 ' + str(pending) + ' 个待处理任务')
        processed = worker.tick()
        if args.command == 'once':
            report('本次处理结束：' + str(len(processed)) + ' 个任务；不会重跑已完成诊断')
        if args.command == 'once':
            break
        time.sleep(5)

if __name__ == '__main__':
    main()
