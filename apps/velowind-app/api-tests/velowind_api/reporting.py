"""Allure output for CLI runs; attachments contain only the sanitized run journal."""
import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4
from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import Attachment, Label, StatusDetails, TestResult, TestStepResult


def write_allure(report, directory, *, config_only=False):
    logger = AllureFileLogger(directory)
    name = "私聊接口配置检查" if config_only else "私聊：未读、文本、置顶隐藏、笔记活动分享"
    full_name = "velowind_api.config_check" if config_only else "velowind_api.private_chat"
    status = {"passed": "passed", "config_validated": "passed", "blocked": "broken"}.get(report["status"], "failed")
    if report.get("error_type") not in (None, "AssertionError") and status == "failed":
        status = "broken"
    attachment = str(uuid4()) + "-attachment.json"
    logger.report_attached_data(json.dumps(report, ensure_ascii=False, indent=2), attachment)
    def api_step(call):
        attachments = []
        for kind in ("request", "response"):
            if kind not in call:
                continue  # Older journals did not capture payloads.
            filename = str(uuid4()) + "-attachment.json"
            logger.report_attached_data(json.dumps(call[kind], ensure_ascii=False, indent=2), filename)
            attachments.append(Attachment(name=kind, source=filename, type="application/json"))
        return TestStepResult(name=f"{call['method']} {call['path']}",
            status="passed" if call["status"] == "passed" else "broken", stage="finished",
            start=call.get("start"), stop=call.get("stop"), attachments=attachments)

    steps = []
    for item in report["steps"]:
        step_status = item["status"]
        if step_status == "failed" and item.get("error_type") != "AssertionError":
            step_status = "broken"
        steps.append(TestStepResult(
            name=item["name"], status=step_status, stage="finished",
            steps=[api_step(call) for call in report["requests"][item.get("request_start", 0):item.get("request_stop", 0)]],
            start=item.get("start"), stop=item.get("stop"),
            statusDetails=StatusDetails(message=item.get("error", item.get("error_type")))
            if item.get("error_type") else None,
        ))
    logger.report_result(TestResult(
        uuid=str(uuid4()), name=name, fullName=full_name,
        historyId=hashlib.sha256(full_name.encode()).hexdigest(),
        testCaseId=hashlib.sha256(full_name.encode()).hexdigest(),
        status=status, stage="finished", start=report.get("start"), stop=int(time.time() * 1000),
        statusDetails=StatusDetails(message=report["error"]) if report.get("error") else None,
        steps=steps, attachments=[Attachment(name="脱敏请求与断言结果（含清理状态）", source=attachment, type="application/json")],
        labels=[Label(name="parentSuite", value="Velowind API"), Label(name="suite", value="私聊"),
                Label(name="feature", value="私聊后端服务"), Label(name="framework", value="Python API")],
    ))
    for path in Path(directory).glob("*.json"):
        path.chmod(0o600)
