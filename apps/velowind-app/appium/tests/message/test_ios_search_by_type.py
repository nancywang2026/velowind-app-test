import pytest

from velowind_appium.modules import (
    browse_note_feed,
    note_feed_contains_type_results,
    select_note_type,
    switch_note_type_navigation,
    wait_for_note_type_results,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


# NOTE_TYPE = "徒步"
NOTE_TYPE = "骑行"


@pytest.mark.full
def test_user_can_filter_notes_by_type(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))
    step("browse-note-feed", lambda: browse_note_feed(driver, timeout=20))
    step("switch-note-type-navigation", lambda: switch_note_type_navigation(driver, timeout=8))
    step("select-hiking-type", lambda: select_note_type(driver, NOTE_TYPE, timeout=10))
    step("wait-hiking-note-results", lambda: wait_for_note_type_results(driver, NOTE_TYPE, timeout=8))

    assert note_feed_contains_type_results(
        driver.page_source,
        NOTE_TYPE,
    ), f"Expected the note feed to include {NOTE_TYPE} related notes"
