from __future__ import annotations

import json
from pathlib import Path
import time

from .agent import CodexAgent
from .repair import apply_patch, check_patch, cleanup_status, device_busy, prepare_worktree, run_tests
from .store import APP, Store, QueueBusyError, git, redact, write_json
from . import allure_results
from .taiga import Taiga


class Worker:
    def __init__(self, repo, queue, config, agent=None, reporter=None):
        self.report = reporter or (lambda message: None)
        self._busy_reported = False
        self.repo, self.store, self.config = Path(repo).resolve(), Store(queue), config
        self.agent = agent or CodexAgent(self.repo / '.agents/skills/appium-ai-triage/SKILL.md',
                                         timeout=min(int(config.get('ai_timeout', 300)), 600),
                                         auth_mode=config.get('agent_auth_mode', 'chatgpt'))

    def context(self, job, source=None):
        from .evidence import Evidence
        return Evidence(self.repo, self.store.root / job['id'], job, self.config, source).initial()

    def diagnose(self, job):
        from .evidence import Evidence
        evidence = Evidence(self.repo, self.store.root / job['id'], job, self.config)
        evidence.initial()
        limit = max(0, min(int(self.config.get('max_evidence_rounds', 2)), 4))
        deadline = time.monotonic() + min(int(self.config.get('diagnosis_timeout', 600)), 1200)
        prior = []
        request_history = []
        for round_number in range(limit + 1):
            if time.monotonic() >= deadline:
                self.store.update(job['id'], 'running', evidence_stop='Diagnosis time budget exhausted')
                break
            # The timeout of each actual model call also respects the remaining total budget.
            if isinstance(self.agent, CodexAgent):
                self.agent.timeout = max(1, min(int(self.config.get('ai_timeout', 300)), int(deadline - time.monotonic())))
            self.report('AI 诊断轮次 ' + str(round_number + 1) + '；补证上限 ' + str(limit))
            directory = self.store.root / job['id'] / ('diagnosis-' + str(time.time_ns()))
            context = dict(evidence.context(), previous_diagnoses=prior)
            write_json(directory / 'context.json', context)
            diagnosis = (self.agent.ask('diagnose', context, audit_directory=directory)
                         if isinstance(self.agent, CodexAgent) else self.agent.ask('diagnose', context))
            write_json(directory / 'answer.json', diagnosis)
            prior.append(diagnosis)
            self.store.update(job['id'], 'running', diagnosis=diagnosis,
                              evidence_rounds=round_number, evidence_manifest=evidence.items,
                              diagnosis_context=str(directory / 'context.json'))
            requests = diagnosis.get('evidence_requests', [])
            if diagnosis['decision'] != 'request_evidence' and not requests:
                return diagnosis
            if round_number == limit:
                self.store.update(job['id'], 'running', evidence_stop='Evidence round budget exhausted')
                return diagnosis
            obtained = False
            before = len(evidence.items)
            for request in requests[:6]:
                obtained = evidence.request(request) or obtained
            request_history.extend(requests[:6])
            self.store.update(job['id'], 'running', evidence_manifest=evidence.items,
                              evidence_requests=request_history)
            if not obtained:
                self.store.update(job['id'], 'running', evidence_stop='Repeated, unavailable or rejected evidence; no new content',
                                  evidence_responses=evidence.items[before:])
                return diagnosis
        return prior[-1]

    def process(self, job_id, *, resume=False, rediagnose=False, diagnose_only=False):
        with self.store.lock():
            job = self.store.get(job_id)
            if resume:
                if job['state'] in {'ready_for_review', 'bug_filed'}:
                    raise ValueError('Completed job cannot be replayed')
                self.store.update(job_id, 'queued', **({'diagnosis': None, 'evidence_stop': '', 'evidence_rounds': 0, 'evidence_requests': []} if rediagnose else {}))
                job = self.store.get(job_id)
            if job['state'] not in {'queued', 'waiting_device', 'waiting_evidence', 'bug_retry', 'repairing', 'running'}:
                return job
            directory = self.store.root / job_id
            try:
                self.report('开始任务 ' + job_id + '：' + job['payload']['nodeid'])
                self.store.update(job_id, 'running', reason='Processing failure evidence')
                diagnosis = job['result'].get('diagnosis')
                if diagnosis is None:
                    self.report('正在调用 Codex 诊断；超时上限 ' + str(self.config.get('ai_timeout', 300)) + ' 秒')
                    diagnosis = self.diagnose(job)
                    self.store.update(job_id, 'running', diagnosis=diagnosis)
                job = self.store.get(job_id)
                from .evidence import has_blockers
                if has_blockers(diagnosis) or not diagnosis['evidence'] or diagnosis['decision'] in {'manual', 'request_evidence'}:
                    self.store.update(job_id, 'needs_human', reason=job['result'].get('evidence_stop') or 'Diagnosis has blocking uncertainty, missing evidence or explicit manual decision')
                elif diagnose_only:
                    self.store.update(job_id, 'diagnosed', reason='Diagnosis only; no repair, device retry or external submission')
                elif diagnosis['category'] == 'automation_defect':
                    self.repair(job, diagnosis, directory)
                elif diagnosis['category'] == 'product_defect':
                    self.bug(job, diagnosis, directory)
                else:
                    self.store.update(job_id, 'needs_human', reason='Environment/data/unknown: no blind side-effect retries')
            except Exception as error:
                self.store.update(job_id, 'needs_human', reason=type(error).__name__ + ': ' + redact(str(error))[:1500])
            self.journal(job_id)
            self.publish_allure(job_id)
            final = self.store.get(job_id)
            diagnosis = final['result'].get('diagnosis') or {}
            self.report('任务 ' + job_id + ' → ' + final['state'] + ' / ' + diagnosis.get('category', '未分类'))
            self.report('原因：' + ' '.join(redact(final['result'].get('reason', '')).split())[:350])
            self.report('结果：' + str(self.store.root / job_id / 'handoff.md'))
            return final

    def journal(self, job_id):
        job = self.store.get(job_id)
        text = ('# AI failure triage ' + job_id + '\n\n'
                '## 范围与当前状态\n\n' + job['state'] + '\n\n'
                '## 失败证据\n\n原始失败、报告及截图路径见下面 payload；缺失项未验证。\n\n'
                '## 本轮分析、修改与验证\n\n'
                '已确认事实见执行结果；AI diagnosis 为分析结论，未执行的验证不可视为通过。\n'
                '断言、清理、真机验证分别记录；分支不自动提交、推送或合并。\n\n```json\n' +
                redact(json.dumps(job, ensure_ascii=False, indent=2)) + '\n```\n\n'
                '## 遗留项与交接\n\n见 reason / cleanup / device_validation；unknown 表示未验证。\n')
        with (self.store.root / job_id / 'handoff.md').open('a') as stream:
            stream.write('\n\n' + text)
        worktree = job['result'].get('worktree')
        if worktree and Path(worktree).exists():
            root = Path(worktree) / APP / 'docs/test-fixes'
            root.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            from zoneinfo import ZoneInfo
            date = datetime.fromtimestamp(job['created'], ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
            name = date + '-ai-triage-' + job['fingerprint'] + '.md'
            with (root / name).open('a') as stream:
                stream.write('\n\n' + text)
            index = root / 'README.md'
            if index.exists() and name not in index.read_text():
                with index.open('a') as stream:
                    stream.write('\n- [AI triage ' + job['fingerprint'] + '](' + name + ')：详见逐轮记录，断言/清理/真机结果分列。\n')

    def repair(self, job, diagnosis, directory):
        from .evidence import has_blockers
        job_id = job['id']
        related = [self.store.get(row['id']) for row in self.store.list()
                   if row['id'] != job_id and row['fingerprint'] == job['fingerprint']]
        previous = next((x for x in related if x['result'].get('branch')), None)
        if previous:
            self.store.update(job_id, 'needs_human', related_job=previous['id'],
                              branch=previous['result']['branch'],
                              reason='Existing issue branch retained; continue the original job')
            return
        worktree, branch = prepare_worktree(self.repo, self.store, job)
        if not job['result'].get('unit_verified') and git(worktree, 'diff', '--stat', '--', APP + '/velowind_appium', APP + '/tests'):
            raise ValueError('Interrupted patch present; reconcile original attempt before continuing')
        validation = self.config.get('validation', {}).get(job['payload']['nodeid'])
        if not validation or not validation.get('unit'):
            self.store.update(job_id, 'needs_human', reason='Configure explicit unit and impacted device coverage', branch=branch)
            return
        attempts = int(job['result'].get('attempts', 0))
        if not job['result'].get('unit_verified'):
            if attempts >= min(int(self.config.get('max_attempts', 2)), 2):
                self.store.update(job_id, 'needs_human', reason='Repair attempt limit reached')
                return
            attempt = directory / ('attempt-' + str(attempts + 1))
            attempt.mkdir(exist_ok=True)
            # Record attempt before invoking AI; crashes consume budget, not free retries.
            self.store.update(job_id, 'repairing', attempts=attempts + 1)
            context = self.context(job, worktree)
            context['diagnosis'] = diagnosis
            context['previous_failure'] = job['result'].get('previous_failure')
            patch = self.agent.ask('repair', context)
            write_json(attempt / 'proposal.json', patch)
            if patch['decision'] != 'propose' or has_blockers(patch) or not patch['assertions_preserved']:
                raise ValueError('Repair did not meet evidence and assertion requirements')
            (attempt / 'proposal.patch').write_text(patch['patch'])
            paths = check_patch(worktree, patch['patch'])
            review_context = dict(context, proposed_patch=patch['patch'])
            review = self.agent.ask('review', review_context)
            write_json(attempt / 'review.json', review)
            if review['decision'] != 'accept' or not review['assertions_preserved'] or has_blockers(review):
                raise ValueError('Independent AI review requires human assessment')
            apply_patch(worktree, patch['patch'], paths)
            unit = run_tests(worktree, validation['unit'], attempt / 'unit',
                             min(int(self.config.get('unit_timeout', 300)), 600), repo=self.repo)
            self.store.update(job_id, 'repairing', unit=unit, patch=str(attempt / 'proposal.patch'))
            if not unit['passed']:
                import subprocess
                subprocess.run(['git', '-C', str(worktree), 'apply', '-R', '-'],
                               input=patch['patch'], text=True, capture_output=True, check=True)
                self.store.update(job_id, 'repairing', previous_failure=redact((attempt / 'unit/pytest.log').read_text())[-12000:])
                self.repair(self.store.get(job_id), diagnosis, directory)
                return
            self.store.update(job_id, 'repairing', unit_verified=True)
        if not validation.get('device') or job['payload']['nodeid'] not in validation['device']:
            self.store.update(job_id, 'needs_human', reason='Device coverage must include original failed selector')
            return
        # Side-effect policy is trusted configuration, never chosen by AI.
        if not validation.get('safe_to_rerun', False):
            self.store.update(job_id, 'needs_human', reason='Business side-effect/precondition policy not established',
                              assertions='unit_passed', device_validation='not_run', cleanup='unknown')
            return
        if device_busy():
            self.store.update(job_id, 'waiting_device', reason='Existing test runner active; no session replaced')
            return
        # A crash after starting a device retry must not replay mutations automatically.
        if job['result'].get('device_started'):
            self.store.update(job_id, 'needs_human', reason='Previous device run interrupted; reconcile data before retry')
            return
        self.store.update(job_id, 'repairing', device_started=True)
        device_dir = directory / 'device'
        result = run_tests(worktree, validation['device'], device_dir,
                           min(int(self.config.get('device_timeout', 1800)), 3600),
                           device=True, platform=job['payload']['platform'], repo=self.repo)
        self.store.update(job_id, 'ready_for_review' if result['passed'] else 'needs_human',
                          device=result, assertions='passed' if result['passed'] else 'failed',
                          device_validation='passed' if result['passed'] else 'failed',
                          cleanup=cleanup_status(device_dir), branch=branch,
                          reason='Branch retained; no automatic commit, push or merge')

    def bug(self, job, diagnosis, directory):
        job_id = job['id']
        if not diagnosis['expected'] or not diagnosis['actual'] or not diagnosis['steps']:
            raise ValueError('Product bug requires expected/actual behavior and reproduction steps')
        draft = {'subject': diagnosis['summary'][:200], 'description': redact(
            '\n'.join(['Expected: ' + diagnosis['expected'], 'Actual: ' + diagnosis['actual'],
                       'Steps:', *diagnosis['steps'], 'Evidence:', *diagnosis['evidence'],
                       'Selector: ' + job['payload']['nodeid'],
                       'Platform: ' + job['payload']['platform'], 'Commit: ' + job['payload']['commit'],
                       'Runtime metadata (missing means unknown): ' + json.dumps(job['payload']['metadata'], ensure_ascii=False),
                       'Cleanup: unknown', 'Screenshot confirms only its visible state; full reproduction not inferred.']))}
        write_json(directory / 'bug-draft.json', draft)
        evidence_file = directory / 'reviewed-evidence.json'
        if not evidence_file.exists():
            self.store.update(job_id, 'waiting_evidence', reason='Review relevant PNG privacy and current-device state before upload')
            return
        evidence = json.loads(evidence_file.read_text())
        import hashlib
        if evidence.get('device_state') == 'connected_current_captured' and time.time() - evidence.get('reviewed_at', 0) > 300:
            self.store.update(job_id, 'waiting_evidence', reason='Connected-device screenshot review expired; recapture relevant current frame')
            return
        attachments = []
        for entry in evidence.get('screenshots', []):
            path = Path(entry['path']).resolve()
            if not path.is_relative_to(directory.resolve()) or path.suffix.lower() != '.png':
                raise ValueError('Reviewed evidence must be a PNG inside this job directory')
            content = path.read_bytes()
            if not content.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(content).hexdigest() != entry.get('sha256'):
                raise ValueError('Reviewed screenshot changed or invalid PNG')
            if entry.get('privacy_reviewed') is not True or entry.get('related') is not True:
                raise ValueError('Screenshot lacks privacy/relevance review')
            attachments.append(path)
        # Phone disconnected is allowed if recorded honestly; connected needs a fresh reviewed frame.
        if not attachments or evidence.get('device_state') not in {'disconnected', 'connected_current_captured'}:
            raise ValueError('Missing screenshots or current phone state review')
        taiga_config = self.config.get('taiga')
        if not taiga_config:
            self.store.update(job_id, 'needs_human', reason='Bug draft ready; Taiga project/API configuration missing')
            return
        try:
            result = Taiga(taiga_config).submit(job, draft, attachments)
        except Exception as error:
            self.store.update(job_id, 'bug_retry', reason='Taiga delivery incomplete: ' + type(error).__name__)
            return
        self.store.update(job_id, 'bug_filed', bug=result, assertions='failed', cleanup='unknown')

    def publish_allure(self, job_id):
        job = self.store.get(job_id)
        try:
            outcome = allure_results.publish(self.store, job)
            if outcome['status'] == 'pending':
                if not job['result'].get('allure_pending'):
                    self.store.update(job_id, job['state'], allure_pending=True)
                    self.report('Allure 用例尚未落盘，等待测试结束后回写')
                return
            if job['result'].get('allure_pending'):
                self.store.update(job_id, job['state'], allure_pending=False)
            if outcome['status'] == 'published':
                self.report('AI 诊断附件已写入对应 Allure 用例')
                if outcome.get('report') and self.config.get('allure_refresh', True):
                    self.report('正在刷新 Allure HTML 报告')
                    refreshed = allure_results.refresh(job['payload']['metadata']['allure_results_dir'], outcome['report'])
                    self.store.update(job_id, job['state'], allure_refresh=refreshed)
                    self.report('Allure：' + refreshed + '；已打开页面请刷新')
        except Exception as error:
            self.store.update(job_id, job['state'], allure_pending=False,
                              allure_publish_error=redact(str(error))[:500])
            self.report('Allure 回写未完成：' + type(error).__name__ + '；诊断结果仍已保留')

    def tick(self):
        processed = []
        for row in self.store.list():
            if row['state'] in {'queued', 'waiting_device'}:
                try:
                    processed.append(self.process(row['id']))
                    self._busy_reported = False
                except QueueBusyError:
                    if not self._busy_reported:
                        self.report('其他 worker 正在处理该队列，本次不重复调用 AI')
                        self._busy_reported = True
                    break
        # Retry only report publication, never rerun AI or business operations.
        for row in self.store.list():
            job = self.store.get(row['id'])
            if job['result'].get('allure_pending'):
                try:
                    with self.store.lock():
                        self.publish_allure(job['id'])
                except QueueBusyError:
                    break
        return processed
