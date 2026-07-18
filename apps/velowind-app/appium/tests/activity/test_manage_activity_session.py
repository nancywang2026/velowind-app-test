import pytest

from velowind_appium.modules.activity_sessions import add_activity_session, build_activity_session_draft
from velowind_appium.reporting import attach_text


@pytest.mark.full
@pytest.mark.skip_home_session
def test_user_can_add_activity_session_from_my_approved_activity(driver, ios_config, step):
    draft = build_activity_session_draft()

    success_signal = step(
        "add-activity-session",
        lambda: add_activity_session(driver, draft, ios_config, timeout=90),
    )

    attach_text(
        "activity-session-verification-points",
        "\n".join(
            [
                "1. 已进入我的活动发布列表",
                "2. 已勾选/打开显示下架活动",
                "3. 已打开通过活动的管理场次入口",
                "4. 已新增场次并填写全部可见字段",
                f"5. 成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal
