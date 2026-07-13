import pytest

from velowind_appium.modules import (
    choose_save_draft,
    fill_note_draft_title,
    go_back_from_note_editor,
    me_page_is_visible,
    open_me_page,
    open_note_draft_editor,
    save_draft_dialog_is_visible,
    wait_for_save_draft_dialog,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_for_publish_entry


NOTE_DRAFT_TITLE = "自动化草稿标题"


@pytest.mark.full
def test_user_can_save_note_as_draft_and_open_me_page(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)

    step("prepare-home-session", lambda: ensure_logged_in_for_publish_entry(driver, ios_config))
    step("open-note-draft-editor", lambda: open_note_draft_editor(driver, ios_config=ios_config, timeout=20))
    step("fill-note-draft-title", lambda: fill_note_draft_title(driver, NOTE_DRAFT_TITLE, timeout=12))
    step("go-back-from-note-editor", lambda: go_back_from_note_editor(driver, timeout=10))
    step("wait-save-draft-dialog", lambda: wait_for_save_draft_dialog(driver, timeout=10))
    assert save_draft_dialog_is_visible(driver.page_source), "Expected the save draft dialog to become visible"
    step("choose-save-draft", lambda: choose_save_draft(driver, timeout=10))
    step("open-me-page", lambda: open_me_page(driver, timeout=12))

    assert me_page_is_visible(driver.page_source), "Expected to enter the Me page after saving the draft"
