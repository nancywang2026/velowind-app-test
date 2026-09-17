from datetime import date, timedelta

import pytest

from velowind_appium.modules.activity_sessions import add_activity_session, build_activity_session_draft
from velowind_appium.reporting import attach_text


@pytest.mark.full
@pytest.mark.skip_home_session
def test_user_can_add_activity_session_from_my_approved_activity(driver, ios_config, step):
    today = date.today()
    draft = build_activity_session_draft(today=today)

    success_signal = step(
        "add-activity-session",
        lambda: add_activity_session(driver, draft, ios_config, timeout=90, manage_timeout=180),
    )

    attach_text(
        "activity-session-verification-points",
        "\n".join(
            [
                "1. 已进入我的活动发布列表",
                "2. 已找到通过且上架的活动",
                "3. 已打开通过活动的管理场次入口",
                "4. 已新增场次并填写全部可见字段",
                f"5. 成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal
