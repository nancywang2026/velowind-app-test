import pytest

from velowind_appium.modules import browse_note_detail, open_first_note_search_result, open_note_search, search_notes
from velowind_appium.session import dismiss_common_system_alerts

from .test_android_feature_walkthrough import prepare_android_home


SEARCH_KEYWORD = "骑行"


@pytest.mark.android_smoke
def test_android_user_can_search_and_open_note(android_driver, step):
    dismiss_common_system_alerts(android_driver, step)
    assert prepare_android_home(android_driver, step)

    step("open-note-search", lambda: open_note_search(android_driver, timeout=15))
    step("search-notes", lambda: search_notes(android_driver, SEARCH_KEYWORD, timeout=15))
    step("open-first-search-result", lambda: open_first_note_search_result(android_driver, timeout=20))
    snapshot = step("browse-note-detail", lambda: browse_note_detail(android_driver, timeout=20))

    assert snapshot.title, "Expected the searched note detail to expose a title"
    assert snapshot.body, "Expected the searched note detail to expose content"
