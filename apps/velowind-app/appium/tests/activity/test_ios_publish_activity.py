import pytest

from velowind_appium.modules import build_activity_draft, publish_activity
from velowind_appium.reporting import attach_text
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@pytest.mark.full
def test_user_can_publish_activity_for_review(driver, ios_config, step):
    draft = build_activity_draft()

    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    success_signal = step(
        "publish-activity-for-review",
        lambda: publish_activity(driver, draft, ios_config=ios_config, timeout=90),
    )

    attach_text(
        "activity-publish-verification-points",
        "\n".join(
            [
                "1. 已进入首页并完成登录态准备",
                "2. 已从底部加号/发布入口进入活动发布流程",
                "3. 已填写活动标题、描述及可见必填信息",
                f"4. 已提交审核并拿到成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal, "Expected a success signal after submitting the activity for review"
    assert any(token in success_signal for token in ["成功", "审核", "待审核", "我的活动"]), (
        f"Expected the publish flow to end in a success/review state, got: {success_signal}"
    )
