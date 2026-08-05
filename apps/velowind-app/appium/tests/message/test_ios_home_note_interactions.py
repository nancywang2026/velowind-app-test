from datetime import datetime

import pytest

from velowind_appium.modules import (
    browse_note_detail,
    browse_note_feed,
    favorite_note,
    like_note,
    message_detail_is_visible,
    submit_message_comment,
    tap_note_card_at_ordinal,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


LOADING_DETAIL_TEXTS = ("正在加载", "正在加载真实详情内容")


def _open_home_note(driver, ios_config, step, *, ordinal: int):
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("browse-note-feed", lambda: browse_note_feed(driver, timeout=20))

    def _return_to_feed_after_unready_detail():
        driver.back()
        browse_note_feed(driver, timeout=15)

    def _open_ready_card():
        errors = []
        for candidate_ordinal in range(ordinal, ordinal + 4):
            opened = tap_note_card_at_ordinal(
                driver,
                ordinal=candidate_ordinal,
                page_source=driver.page_source,
                verify_open=lambda: message_detail_is_visible(driver),
                timeout=3,
            )
            if not opened:
                errors.append(f"ordinal {candidate_ordinal}: card did not open")
                continue
            try:
                return browse_note_detail(driver, timeout=20)
            except AssertionError as error:
                page_source = driver.page_source
                if not any(text in page_source for text in LOADING_DETAIL_TEXTS):
                    raise
                errors.append(f"ordinal {candidate_ordinal}: detail stayed on loading placeholder")
                _return_to_feed_after_unready_detail()
        raise AssertionError(
            f"Unable to open a ready home note detail from ordinal {ordinal}; " + "; ".join(errors)
        )

    return step(f"open-ready-home-note-{ordinal}", _open_ready_card)


@pytest.mark.full
def test_user_can_comment_on_first_home_note(driver, ios_config, step):
    snapshot = _open_home_note(driver, ios_config, step, ordinal=1)
    assert snapshot.title, "Expected the first home note detail to expose a title"

    comment_text = f"测试 - 这条笔记不错！！ {datetime.now():%m%d%H%M%S}"
    step("add-note-comment", lambda: submit_message_comment(driver, comment_text, timeout=20))


@pytest.mark.full
def test_user_can_like_and_favorite_second_home_note(driver, ios_config, step):
    snapshot = _open_home_note(driver, ios_config, step, ordinal=2)
    assert snapshot.title, "Expected the second home note detail to expose a title"

    like_counts = step("like-note", lambda: like_note(driver, timeout=15))
    favorite_counts = step("favorite-note", lambda: favorite_note(driver, timeout=15))

    assert like_counts[0] != like_counts[1], "Expected the like state/count to change after tapping like"
    assert favorite_counts[0] != favorite_counts[1], "Expected the favorite state/count to change after tapping favorite"
