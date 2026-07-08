import pytest

from velowind_appium.modules import build_changbaishan_note_draft, publish_message_note
from velowind_appium.reporting import attach_text
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@pytest.mark.full
def test_user_can_publish_changbaishan_note_for_review(driver, ios_config, step):
    draft = build_changbaishan_note_draft()

    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    success_signal = step(
        "publish-changbaishan-note-for-review",
        lambda: publish_message_note(driver, draft, ios_config=ios_config, timeout=90),
    )

    attach_text(
        "message-note-publish-verification-points",
        "\n".join(
            [
                "1. 已进入首页并完成登录态准备",
                "2. 已从底部加号/发布入口进入笔记发布流程",
                f"3. 已填写标题: {draft.title}",
                f"4. 已填写话题: {' '.join(draft.topics)}",
                f"5. 已标记地点: {draft.location}",
                f"6. 已设置允许评论: {'是' if draft.allow_comments else '否'}",
                f"7. 已提交并拿到成功信号: {success_signal}",
            ]
        ),
    )

    assert success_signal, "Expected a success signal after submitting the message note for review"
    assert any(token in success_signal for token in ["成功", "审核", "待审核"]), (
        f"Expected the note publish flow to end in a success/review state, got: {success_signal}"
    )
