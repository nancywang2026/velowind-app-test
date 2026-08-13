import pytest

from tests.conftest import prepare_logged_in_session
from velowind_appium.modules.message_detail import (
    MessageNoteDraft,
    message_note_form_is_visible,
    open_message_note_publisher,
    _choose_note_image_from_library,
)
from velowind_appium.modules.message_detail import _record_note_selected_album_image_source


@pytest.mark.full
def test_ios_publish_note_photo_returns_to_form(driver, ios_config, step):
    draft = MessageNoteDraft(
        title="测试图片回传",
        body="测试图片回传",
        topics=[],
        location="",
        album="图片",
        picture_index=1,
        allow_comments=True,
    )

    step("prepare-home-session", lambda: prepare_logged_in_session(driver, ios_config))
    step("open-publisher", lambda: open_message_note_publisher(driver, ios_config=ios_config, timeout=60))
    step(
        "choose-photo-and-return",
        lambda: _choose_note_image_from_library(
            driver,
            album_name=draft.album,
            picture_index=draft.picture_index,
            picture_indexes=(),
            select_all_from_album=False,
        ),
    )
    step(
        "record-selected-source",
        lambda: _record_note_selected_album_image_source(driver, draft),
    )

    assert message_note_form_is_visible(driver.page_source)
    assert getattr(driver, "_publish_note_album_source_image_path", None) is not None
