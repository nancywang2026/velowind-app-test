"""Opt in via VW_API_DATA and optionally VW_API_ENVIRONMENT. Never auto-runs."""
import json
import os
from pathlib import Path
import pytest
import allure
from velowind_api.config import ConfigError, load_config
from velowind_api.scenario import new_report, run


@allure.suite("私聊 API")
@allure.title("私聊：未读、文本、置顶隐藏、笔记活动分享")
@pytest.mark.live
def test_private_chat_live():
    if not os.environ.get("VW_API_DATA"):
        pytest.skip("Live API not configured: set VW_API_DATA and VW_API_ENVIRONMENT")
    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.fail("Private chat requires serial execution")
    report = new_report()
    try:
        data = load_config(os.environ["VW_API_DATA"], os.environ.get("VW_API_ENVIRONMENT"))
        run(data, report)
    except ConfigError:
        report["status"] = "blocked"
        raise
    finally:
        target = Path(os.environ.get("VW_API_REPORT", ".tmp/private-chat-api/report.json"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        target.chmod(0o600)
        allure.attach(json.dumps(report, ensure_ascii=False, indent=2), "脱敏请求与断言结果", allure.attachment_type.JSON)
