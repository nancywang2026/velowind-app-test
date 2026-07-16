from velowind_appium.modules import message_detail
from pathlib import Path
import pytest
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from velowind_appium.modules.message_detail import (
    build_changbaishan_note_draft,
    list_message_note_use_case_ids,
    load_message_note_draft,
    message_note_form_is_visible,
    message_note_publish_error_signal,
    message_note_publish_success_signal,
    parse_detail_snapshot,
)


def test_android_note_search_coordinate_targets_visible_header_icon():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_search_entry_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 972, "y": 216})]


def test_android_note_search_submit_targets_visible_header_action():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_search_submit_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 972, "y": 216})]


def test_find_note_search_input_supports_android_edit_text():
    expected = object()

    class FakeDriver:
        @staticmethod
        def find_element(by, value):
            if value == '//android.widget.EditText[contains(@hint, "请输入内容")]':
                return expected
            raise NoSuchElementException("no match")

    assert message_detail._find_note_search_input(FakeDriver(), timeout=0.1) is expected


def test_android_note_search_results_accept_hidden_keyword_matches():
    page_source = """
    <hierarchy>
      <android.widget.EditText text="骑行" hint="请输入内容" />
      <android.widget.TextView text="想去一趟洱海，想顺便把自己也放空一下" />
      <android.widget.TextView text="#云南洱海" />
      <android.widget.TextView text="用户 15aa909316f54c2b8671dc3c35476559" />
    </hierarchy>
    """

    assert message_detail._note_search_results_visible(page_source, "骑行") is True


def test_tap_note_search_result_tries_next_card_when_first_does_not_open(monkeypatch):
    events = []

    class FakeDriver:
        def find_element(self, by, value):
            raise message_detail.NoSuchElementException("missing")

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "search-results")
    monkeypatch.setattr(
        message_detail,
        "tap_first_note_card",
        lambda driver, page_source, verify_open, timeout=1.2: events.append("first") or False,
    )
    monkeypatch.setattr(
        message_detail,
        "tap_note_card_at_ordinal",
        lambda driver, ordinal, page_source, verify_open, timeout=1.2: events.append(ordinal) or ordinal == 2,
        raising=False,
    )
    monkeypatch.setattr(message_detail, "_tap_accessibility_id_now", lambda driver, value: False)
    monkeypatch.setattr(message_detail, "_tap_first_visible_note_search_result", lambda driver: False)
    monkeypatch.setattr(message_detail, "_tap_first_note_search_result_by_coordinate", lambda driver: False)

    assert message_detail._tap_first_note_search_result(FakeDriver()) is True
    assert events == ["first", 2]


def test_tap_note_search_result_scrolls_to_next_result_page(monkeypatch):
    events = []
    state = {"page": "page-1"}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(
        message_detail,
        "tap_first_note_card",
        lambda driver, page_source, verify_open, timeout=1.2: events.append(("first", page_source))
        or page_source == "page-2",
    )
    monkeypatch.setattr(
        message_detail,
        "tap_note_card_at_ordinal",
        lambda driver, ordinal, page_source, verify_open, timeout=1.2: events.append((ordinal, page_source)) or False,
    )
    monkeypatch.setattr(
        message_detail,
        "swipe_vertical",
        lambda driver, direction="up": events.append(("swipe", direction)) or state.update(page="page-2"),
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._tap_first_note_search_result(object()) is True
    assert ("swipe", "up") in events
    assert events[-1] == ("first", "page-2")


def test_parse_android_detail_snapshot_extracts_text_and_bottom_counts():
    page_source = """
    <hierarchy>
      <android.widget.FrameLayout resource-id="post-detail-banner-pager" />
      <android.widget.TextView text="想去一趟洱海，想顺便把自己也放空一下" />
      <android.widget.TextView text="#云南洱海 最近总在想，应该去一次洱海，沿着湖边慢慢骑行。" />
      <android.widget.TextView text="Nancy" />
      <android.widget.TextView text="0" bounds="[624,2275][694,2323]" />
      <android.widget.TextView text="0" bounds="[800,2275][871,2323]" />
      <android.widget.TextView text="0" bounds="[976,2275][1047,2323]" />
    </hierarchy>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.title == "想去一趟洱海，想顺便把自己也放空一下"
    assert snapshot.body == "#云南洱海 最近总在想，应该去一次洱海，沿着湖边慢慢骑行。"
    assert snapshot.bottom_action_counts == ["0", "0", "0"]


def test_parse_android_detail_snapshot_reads_count_before_label():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="洱海骑行计划" />
      <android.widget.TextView text="沿着洱海慢慢骑行，记录一路的湖光和晚风。" />
      <android.widget.TextView text="61" />
      <android.widget.TextView text="浏览" />
      <android.widget.TextView text="共 1 条评论" />
      <android.widget.TextView text="自动化评论0715234936" />
    </hierarchy>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.view_count == "61"
    assert snapshot.comment_count == "1"
    assert snapshot.comments == ["自动化评论0715234936"]


def test_browse_android_detail_scrolls_to_load_view_and_comment_metadata(monkeypatch):
    partial = message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"])
    complete = message_detail.MessageDetailSnapshot("标题", "正文", "61", "0", [], "还没有评论", ["0", "0", "0"])
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(message_detail, "read_message_detail_snapshot", lambda driver, timeout: partial)
    monkeypatch.setattr(message_detail, "swipe_vertical", lambda driver, direction: events.append(direction))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "scrolled-detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: complete)

    snapshot = message_detail.browse_note_detail(FakeDriver(), timeout=3)

    assert snapshot.view_count == "61"
    assert snapshot.comment_count == "0"
    assert events == ["up"]

def test_parse_detail_snapshot_extracts_title_counts_and_comments():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="春日骑行计划" label="春日骑行计划" value="春日骑行计划" />
      <XCUIElementTypeStaticText name="这是一次适合周末参加的城市骑行活动内容介绍。" label="这是一次适合周末参加的城市骑行活动内容介绍。" value="这是一次适合周末参加的城市骑行活动内容介绍。" />
      <XCUIElementTypeStaticText name="浏览 128" label="浏览 128" value="浏览 128" />
      <XCUIElementTypeStaticText name="评论 3" label="评论 3" value="评论 3" />
      <XCUIElementTypeStaticText name="用户A：不错，周末见" label="用户A：不错，周末见" value="用户A：不错，周末见" />
      <XCUIElementTypeStaticText name="查看图票" label="查看图票" value="查看图票" />
    </AppiumAUT>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.title == "春日骑行计划"
    assert snapshot.body == "这是一次适合周末参加的城市骑行活动内容介绍。"
    assert snapshot.view_count == "128"
    assert snapshot.comment_count == "3"
    assert snapshot.comments == ["用户A：不错，周末见"]
    assert snapshot.empty_comment_hint is None
    assert snapshot.bottom_action_counts == []


def test_parse_detail_snapshot_extracts_bottom_action_counts():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="用户 abcdef 1 0 3" label="用户 abcdef 1 0 3" />
    </AppiumAUT>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.bottom_action_counts == ["1", "0", "3"]


def test_build_changbaishan_note_draft_uses_requested_content():
    draft = build_changbaishan_note_draft()

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert "第一次去长白山" in draft.body
    assert draft.topics == ["#长白山", "#旅行日记", "#治愈系风景", "#长白山天池", "#东北旅行"]
    assert draft.location == "黑龙江"
    assert draft.album == "长白山"
    assert draft.allow_comments is True


def test_load_message_note_draft_reads_yaml_use_case():
    testdata_path = (
        Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
    )

    draft = load_message_note_draft("publish-note-changbaishan", testdata_path=testdata_path)

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert draft.album == "长白山"
    assert draft.location == "黑龙江"


def test_load_message_note_draft_reads_no_location_variant():
    testdata_path = (
        Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
    )

    draft = load_message_note_draft("publish-note-changbaishan-no-location", testdata_path=testdata_path)

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert draft.album == "长白山"
    assert draft.location == ""


def test_list_message_note_use_case_ids_reads_all_yaml_cases():
    testdata_path = (
        Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
    )

    use_case_ids = list_message_note_use_case_ids(testdata_path=testdata_path)

    assert "publish-note-changbaishan" in use_case_ids
    assert "publish-note-changbaishan-no-location" in use_case_ids
    assert "publish-note-yunnan-erhai" in use_case_ids
    assert "publish-note-hangzhou-hiking" in use_case_ids
    assert "publish-note-beijing-forbidden-city" in use_case_ids


def test_message_note_form_is_visible_from_publish_page_source():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="发布笔记" />
      <XCUIElementTypeTextField name="请输入标题" />
      <XCUIElementTypeTextView name="分享你的旅行故事" />
    </AppiumAUT>
    """

    assert message_note_form_is_visible(page_source) is True


def test_message_note_publish_success_signal_detects_review_state():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="提交成功" />
      <XCUIElementTypeStaticText name="内容审核中" />
    </AppiumAUT>
    """

    assert message_note_publish_success_signal(page_source) == "提交成功"


def test_message_note_publish_success_signal_detects_published_detail_state():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="长白山真的有种让人瞬间安静下来的魔力" />
      <XCUIElementTypeStaticText name="已发布" />
      <XCUIElementTypeStaticText name="共 0 条评论" />
    </AppiumAUT>
    """

    assert message_note_publish_success_signal(page_source) == "已发布"


def test_message_note_publish_error_signal_detects_backend_failure():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="服务开小差了，请稍后重试" />
      <XCUIElementTypeStaticText name="http=500" />
    </AppiumAUT>
    """

    assert message_note_publish_error_signal(page_source) == "服务开小差了，请稍后重试"


def test_fill_message_note_form_uploads_image_and_appends_topics_to_body(monkeypatch):
    events = []
    draft = build_changbaishan_note_draft()

    monkeypatch.setattr(message_detail, "wait_for_message_note_form", lambda driver, timeout: events.append("wait-form"))
    monkeypatch.setattr(message_detail, "_upload_note_image", lambda driver, draft: events.append(("upload-image", draft.album)))
    monkeypatch.setattr(message_detail, "_fill_note_title", lambda driver, title: events.append(("title", title)))
    monkeypatch.setattr(message_detail, "_fill_note_body", lambda driver, body: events.append(("body", body)))
    monkeypatch.setattr(
        message_detail,
        "_append_note_topics_to_body",
        lambda driver, topics: events.append(("body-topics", topics)),
    )
    monkeypatch.setattr(
        message_detail,
        "_fill_note_location",
        lambda driver, location: events.append(("location", location)),
    )
    monkeypatch.setattr(
        message_detail,
        "_set_allow_comments",
        lambda driver, allow_comments: events.append(("allow-comments", allow_comments)),
    )

    message_detail.fill_message_note_form(object(), draft, timeout=60)

    assert events == [
        "wait-form",
        ("upload-image", draft.album),
        ("title", draft.title),
        ("body", draft.body),
        ("body-topics", draft.topics),
        ("location", draft.location),
        ("allow-comments", True),
    ]


def test_fill_message_note_form_skips_location_when_select_location_is_false(monkeypatch):
    events = []
    draft = load_message_note_draft(
        "publish-note-changbaishan-no-location",
        testdata_path=Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml",
    )

    monkeypatch.setattr(message_detail, "wait_for_message_note_form", lambda driver, timeout: events.append("wait-form"))
    monkeypatch.setattr(message_detail, "_upload_note_image", lambda driver, draft: events.append(("upload-image", draft.album)))
    monkeypatch.setattr(message_detail, "_fill_note_title", lambda driver, title: events.append(("title", title)))
    monkeypatch.setattr(message_detail, "_fill_note_body", lambda driver, body: events.append(("body", body)))
    monkeypatch.setattr(
        message_detail,
        "_append_note_topics_to_body",
        lambda driver, topics: events.append(("body-topics", topics)),
    )
    monkeypatch.setattr(
        message_detail,
        "_fill_note_location",
        lambda driver, location: events.append(("location", location)),
    )
    monkeypatch.setattr(
        message_detail,
        "_set_allow_comments",
        lambda driver, allow_comments: events.append(("allow-comments", allow_comments)),
    )

    message_detail.fill_message_note_form(object(), draft, timeout=60)

    assert events == [
        "wait-form",
        ("upload-image", draft.album),
        ("title", draft.title),
        ("body", draft.body),
        ("body-topics", draft.topics),
        ("allow-comments", True),
    ]


def test_browse_note_detail_delegates_to_snapshot_reader(monkeypatch):
    expected = object()
    events = []

    monkeypatch.setattr(
        message_detail,
        "read_message_detail_snapshot",
        lambda driver, timeout=20: events.append(("read-snapshot", timeout)) or expected,
    )

    assert message_detail.browse_note_detail(object(), timeout=18) is expected
    assert events == [("read-snapshot", 18)]


def test_submit_message_note_treats_detail_page_as_success(monkeypatch):
    events = []
    recorded_sources = []
    page_sources = iter([
        "发布笔记 标题 正文",
        "长白山真的有种让人瞬间安静下来的魔力 浏览 评论 写留言",
    ])

    class FakeDriver:
        current_page_source = ""

    driver = FakeDriver()

    def fake_page_source(_driver):
        try:
            driver.current_page_source = next(page_sources)
        except StopIteration:
            pass
        recorded_sources.append(driver.current_page_source)
        return driver.current_page_source

    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(message_detail, "_tap_note_submit", lambda driver: events.append("tap-submit") or True)
    monkeypatch.setattr(message_detail, "_safe_page_source", fake_page_source)
    monkeypatch.setattr(message_detail, "message_note_publish_success_signal", lambda source: None)
    monkeypatch.setattr(message_detail, "message_note_publish_error_signal", lambda source: None)
    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda source: "发布笔记" in source)
    monkeypatch.setattr(message_detail, "message_detail_is_visible", lambda driver: "长白山" in driver.current_page_source)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail.submit_message_note(driver, timeout=3) == "detail-page"
    assert events == ["hide-keyboard", "tap-submit", "hide-keyboard", "tap-submit"]


def test_like_note_toggles_first_bottom_action_and_waits_for_count_change(monkeypatch):
    events = []
    signatures = iter([
        message_detail.MessageDetailSnapshot("标题", "正文", "4", "2", [], None, ["1", "0", "3"]),
        message_detail.MessageDetailSnapshot("标题", "正文", "4", "2", [], None, ["2", "0", "3"]),
    ])

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: next(signatures))
    monkeypatch.setattr(
        message_detail,
        "_tap_bottom_action_at_index",
        lambda driver, action_index: events.append(("tap-bottom-action", action_index)) or True,
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    before, after = message_detail.like_note(driver=object(), timeout=3)

    assert before == ["1", "0", "3"]
    assert after == ["2", "0", "3"]
    assert events == [("tap-bottom-action", 0)]


def test_favorite_note_toggles_second_bottom_action_and_waits_for_count_change(monkeypatch):
    events = []
    signatures = iter([
        message_detail.MessageDetailSnapshot("标题", "正文", "4", "2", [], None, ["1", "0", "3"]),
        message_detail.MessageDetailSnapshot("标题", "正文", "4", "2", [], None, ["1", "1", "3"]),
    ])

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: next(signatures))
    monkeypatch.setattr(
        message_detail,
        "_tap_bottom_action_at_index",
        lambda driver, action_index: events.append(("tap-bottom-action", action_index)) or True,
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    before, after = message_detail.favorite_note(driver=object(), timeout=3)

    assert before == ["1", "0", "3"]
    assert after == ["1", "1", "3"]
    assert events == [("tap-bottom-action", 1)]


def test_android_bottom_action_taps_count_center_by_index():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}
        page_source = """
        <hierarchy>
          <android.widget.FrameLayout resource-id="post-detail-banner-pager" />
          <android.widget.TextView text="10" bounds="[932,1194][968,1236]" />
          <android.widget.TextView text="0" bounds="[999,1686][1019,1726]" />
          <android.widget.TextView text="0" bounds="[624,2275][694,2323]" />
          <android.widget.TextView text="1" bounds="[800,2275][871,2323]" />
          <android.widget.TextView text="2" bounds="[976,2275][1047,2323]" />
        </hierarchy>
        """

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_bottom_action_at_index(FakeDriver(), 2) is True
    assert taps == [("mobile: tap", {"x": 1011, "y": 2299})]


def test_submit_comment_uses_android_bottom_comment_action_when_entry_id_is_missing(monkeypatch):
    events = []

    class FakeInput:
        @staticmethod
        def clear():
            events.append("clear")

        @staticmethod
        def send_keys(value):
            events.append(("send-keys", value))

    candidate_calls = iter([False, True])
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"]))
    monkeypatch.setattr(message_detail, "_tap_candidate", lambda driver, ids, texts: next(candidate_calls))
    monkeypatch.setattr(message_detail, "_tap_bottom_action_at_index", lambda driver, index: events.append(("tap", index)) or True)
    monkeypatch.setattr(message_detail, "_find_comment_input", lambda driver, timeout: FakeInput())
    monkeypatch.setattr(message_detail, "_wait_for_comment_echo", lambda *args, **kwargs: events.append("wait-echo"))

    message_detail.submit_message_comment(object(), "自动化评论", timeout=3)

    assert events == [("tap", 2), "clear", ("send-keys", "自动化评论"), "wait-echo"]


def test_find_comment_input_supports_android_edit_text():
    expected = object()

    class FakeDriver:
        @staticmethod
        def find_element(by, value):
            if value == '//android.widget.EditText[@hint="写留言" or @text="写留言"]':
                return expected
            raise NoSuchElementException("no match")

    assert message_detail._find_comment_input(FakeDriver(), timeout=0.1) is expected


def test_share_note_to_moments_taps_share_then_target(monkeypatch):
    events = []

    monkeypatch.setattr(
        message_detail,
        "_tap_detail_share_button",
        lambda driver: events.append("tap-share") or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_wait_until",
        lambda predicate, timeout: events.append(("wait-until", timeout)) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_share_sheet_visible",
        lambda page_source: True,
    )
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "朋友圈")
    monkeypatch.setattr(
        message_detail,
        "_tap_share_target",
        lambda driver, target_text: events.append(("tap-share-target", target_text)) or True,
    )

    assert message_detail.share_note_to_moments(object(), timeout=6) == "朋友圈"
    assert events == ["tap-share", ("wait-until", 6), ("tap-share-target", "朋友圈")]


def test_open_message_note_publisher_taps_publish_entry_before_note_type(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(message_detail, "login_required_from_page_source", lambda source: False)
    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda source: False)
    monkeypatch.setattr(message_detail, "_tap_publish_entry_if_present", lambda driver: events.append("publish-entry") or True)
    monkeypatch.setattr(message_detail, "_tap_note_type_if_present", lambda driver: events.append("note-type") or True)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    message_detail.open_message_note_publisher(object(), timeout=5)

    assert events[:2] == ["publish-entry", "note-type"]


def test_tap_note_type_uses_android_text_locator(monkeypatch):
    calls = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            raise NoSuchElementException()

    monkeypatch.setattr(message_detail, "_tap_accessibility_id_now", lambda driver, accessibility_id: False)
    monkeypatch.setattr(
        message_detail,
        "tap_text_if_present",
        lambda driver, text, timeout: calls.append((text, timeout)) or text == "笔记",
    )

    assert message_detail._tap_note_type_if_present(FakeDriver()) is True
    assert calls == [("笔记", 1)]


def test_upload_note_image_reports_when_photo_library_does_not_open(monkeypatch):
    draft = build_changbaishan_note_draft()
    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: None)
    monkeypatch.setattr(message_detail, "_tap_note_image_plus", lambda driver: True)
    monkeypatch.setattr(message_detail.photo_picker, "choose_photo_from_library", lambda driver, album_name=None, retry_sheet_option=None: False)

    try:
        message_detail._upload_note_image(object(), draft)
    except AssertionError as error:
        assert "Photo library opened but no selectable photo was found" in str(error)
    else:
        raise AssertionError("Expected upload to fail when the photo library does not open")


def test_upload_note_image_uses_shared_photo_picker(monkeypatch):
    calls = []
    draft = build_changbaishan_note_draft()

    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: calls.append("clear"))
    monkeypatch.setattr(message_detail, "_tap_note_image_plus", lambda driver: calls.append("tap-plus") or True)
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, retry_sheet_option=None: calls.append(
            ("choose-photo", album_name, retry_sheet_option is message_detail._tap_note_photo_library_sheet_option)
        )
        or True,
    )

    message_detail._upload_note_image(object(), draft)

    assert calls == ["clear", "tap-plus", ("choose-photo", "长白山", True)]


def test_android_note_image_plus_taps_first_image_slot_center():
    taps = []

    class FakeElement:
        rect = {"x": 34, "y": 323, "width": 242, "height": 242}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_elements(self, by, value):
            assert value == "//android.widget.HorizontalScrollView//android.view.ViewGroup"
            return [FakeElement()]

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_image_plus(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 155.0, "y": 444.0})]


def test_fill_input_near_label_supports_android_edit_text_hint(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//android.widget.EditText[contains(@hint, "标题") or contains(@text, "标题")]':
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    assert message_detail._fill_input_near_label(FakeDriver(), "标题", "洱海骑行计划") is True
    assert events == ["click", "clear", ("send-keys", "洱海骑行计划"), "hide-keyboard"]


def test_append_note_topics_uses_android_body_edit_text(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("click-body")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//android.widget.EditText[contains(@hint, "正文")]':
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: text == "#话题")
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: events.append("hide-keyboard"))

    message_detail._append_note_topics_to_body(FakeDriver(), ["#云南洱海", "#大理旅行"])

    assert events == [
        "click-body",
        ("send-keys", " #云南洱海 #大理旅行"),
        "hide-keyboard",
    ]


def test_photo_source_option_taps_row_center_from_text_rect():
    taps = []

    class FakeElement:
        rect = {"x": 120, "y": 680, "width": 120, "height": 24}

    class FakeDriver:
        def find_element(self, by, value):
            if "从手机相册选择" in value:
                return FakeElement()
            raise message_detail.NoSuchElementException()

        def get_window_size(self):
            return {"width": 390, "height": 844}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_photo_source_option(FakeDriver(), ["从手机相册选择"]) is True
    assert taps == [("mobile: tap", {"x": 195.0, "y": 692.0})]


def test_choose_local_photo_confirms_cropper_when_present(monkeypatch):
    events = []

    class FakeElement:
        rect = {"x": 20, "y": 140, "width": 120, "height": 120}
    monkeypatch.setattr(message_detail, "_find_photo_grid_candidates", lambda driver: [FakeElement()])

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: events.append("confirm-cropper") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=1, album_name=None) is True
    assert events == [("mobile: tap", {"x": 80.0, "y": 200.0}), "confirm-cropper"]


def test_cropper_confirm_button_taps_button_center():
    taps = []

    class FakeElement:
        rect = {"x": 206, "y": 772, "width": 179, "height": 47}

    class FakeDriver:
        def find_element(self, by, value):
            if "确认裁剪" in value:
                return FakeElement()
            raise message_detail.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_cropper_confirm_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 295.5, "y": 795.5})]


def test_photo_picker_transition_completed_confirms_cropper_once(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "确认裁剪")
    monkeypatch.setattr(message_detail, "_cropper_visible", lambda page_source: True)
    monkeypatch.setattr(
        message_detail,
        "_confirm_note_image_cropper",
        lambda driver, timeout=5: events.append(("confirm-cropper", timeout)) or True,
    )

    assert message_detail._photo_picker_transition_completed(object()) is True
    assert events == [("confirm-cropper", 5)]


def test_photo_picker_transition_completed_skips_cropper_after_first_confirmation(monkeypatch):
    events = []
    driver = type("FakeDriver", (), {"_cropper_confirmed_once": True})()

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "确认裁剪")
    monkeypatch.setattr(message_detail, "_cropper_visible", lambda page_source: True)
    monkeypatch.setattr(
        message_detail,
        "_confirm_note_image_cropper",
        lambda driver, timeout=5: events.append(("confirm-cropper", timeout)) or True,
    )

    assert message_detail._photo_picker_transition_completed(driver) is True
    assert events == []


def test_choose_local_photo_taps_picker_done_when_system_picker_stays_open(monkeypatch):
    events = []

    class FakeElement:
        rect = {"x": 20, "y": 140, "width": 120, "height": 120}
    monkeypatch.setattr(message_detail, "_find_photo_grid_candidates", lambda driver: [FakeElement()])

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: False)
    monkeypatch.setattr(message_detail, "_confirm_system_photo_picker_selection", lambda driver, timeout=10: events.append("picker-done") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=1, album_name=None) is True
    assert events == [("mobile: tap", {"x": 80.0, "y": 200.0}), "picker-done"]


def test_choose_local_photo_prefers_requested_picture_index(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    monkeypatch.setattr(
        message_detail,
        "_find_photo_grid_candidates",
        lambda driver: [
            FakeElement({"x": 20, "y": 140, "width": 120, "height": 120}),
            FakeElement({"x": 160, "y": 140, "width": 120, "height": 120}),
            FakeElement({"x": 300, "y": 140, "width": 120, "height": 120}),
        ],
    )

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=3, album_name=None) is True
    assert events == [("mobile: tap", {"x": 360.0, "y": 200.0})]


def test_choose_local_photo_opens_requested_album_first(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(
        message_detail,
        "_find_photo_grid_selection_badges",
        lambda driver: [
            FakeElement({"x": 116, "y": 136, "width": 17, "height": 17}),
            FakeElement({"x": 215, "y": 136, "width": 17, "height": 17}),
            FakeElement({"x": 314, "y": 136, "width": 17, "height": 17}),
        ],
    )
    monkeypatch.setattr(message_detail, "_open_photo_album", lambda driver, album_name: events.append(("open-album", album_name)) or True)
    monkeypatch.setattr(message_detail, "_confirm_system_photo_picker_selection", lambda driver, timeout=10: events.append("picker-done") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=2, album_name="长白山") is True
    assert events == [
        ("open-album", "长白山"),
        ("mobile: tap", {"x": 124.5, "y": 144.5}),
        ("mobile: tap", {"x": 223.5, "y": 144.5}),
        ("mobile: tap", {"x": 322.5, "y": 144.5}),
        "picker-done",
    ]


def test_android_detail_share_taps_sticky_header_action():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_detail_share_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 1026, "y": 216})]


def test_choose_local_photo_falls_back_to_all_grid_images_when_badges_absent(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "_find_photo_grid_selection_badges", lambda driver: [])
    monkeypatch.setattr(
        message_detail,
        "_find_photo_grid_candidates",
        lambda driver: [
            FakeElement({"x": 0, "y": 142, "width": 133, "height": 133}),
            FakeElement({"x": 134, "y": 142, "width": 134, "height": 133}),
            FakeElement({"x": 269, "y": 142, "width": 133, "height": 133}),
        ],
    )
    monkeypatch.setattr(message_detail, "_open_photo_album", lambda driver, album_name: events.append(("open-album", album_name)) or True)
    monkeypatch.setattr(message_detail, "_confirm_system_photo_picker_selection", lambda driver, timeout=10: events.append("picker-done") or True)

    assert message_detail._choose_local_photo(FakeDriver(), album_name="云南洱海") is True
    assert events == [
        ("open-album", "云南洱海"),
        ("mobile: tap", {"x": 66.5, "y": 208.5}),
        ("mobile: tap", {"x": 201.0, "y": 208.5}),
        ("mobile: tap", {"x": 335.5, "y": 208.5}),
        "picker-done",
    ]


def test_open_photo_album_switches_to_collections_before_switching(monkeypatch):
    events = []
    titles = iter([None, None, "杭州"])

    monkeypatch.setattr(message_detail, "_photo_album_title", lambda driver: next(titles))
    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(message_detail, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or text == "杭州")
    monkeypatch.setattr(message_detail, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._open_photo_album(object(), "杭州") is True
    assert events == [
        ("tap-text", "精选集"),
        ("tap-album", "杭州"),
    ]


def test_open_photo_album_does_not_treat_background_page_text_as_success(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail, "_photo_album_title", lambda driver: "选择最多9张照片。")
    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "精选集")
    monkeypatch.setattr(message_detail, "_tap_named_element_center", lambda driver, text: events.append(("tap-album", text)) or False)
    monkeypatch.setattr(message_detail, "swipe_vertical", lambda driver, direction="up": events.append(("swipe", direction)))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "发布笔记 长白山真的有种让人瞬间安静下来的魔力")
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._open_photo_album(object(), "长白山") is False
    assert events == [
        ("tap-text", "精选集"),
        ("tap-album", "长白山"),
        ("swipe", "up"),
        ("tap-album", "长白山"),
        ("swipe", "up"),
        ("tap-album", "长白山"),
        ("swipe", "up"),
        ("tap-album", "长白山"),
        ("swipe", "up"),
    ]


def test_tap_photo_grid_candidate_uses_rect_snapshot_when_element_stales(monkeypatch):
    class FakeElement:
        def __init__(self):
            self._reads = 0

        @property
        def rect(self):
            self._reads += 1
            if self._reads > 1:
                raise StaleElementReferenceException("stale")
            return {"x": 134, "y": 184, "width": 134, "height": 133}

    taps = []
    monkeypatch.setattr(message_detail, "_find_photo_grid_candidates", lambda driver: [FakeElement()])

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_photo_grid_candidate(FakeDriver(), 1) is True
    assert taps == [("mobile: tap", {"x": 201.0, "y": 250.5})]


def test_find_photo_grid_candidates_keeps_album_images_under_shorter_header():
    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def find_elements(self, by, value):
            return [
                FakeElement({"x": 0, "y": 142, "width": 133, "height": 133}),
                FakeElement({"x": 134, "y": 142, "width": 134, "height": 133}),
                FakeElement({"x": 346, "y": 92, "width": 36, "height": 36}),
            ]

    candidates = message_detail._find_photo_grid_candidates(FakeDriver())

    assert [element.rect for element in candidates] == [
        {"x": 0, "y": 142, "width": 133, "height": 133},
        {"x": 134, "y": 142, "width": 134, "height": 133},
    ]


def test_find_photo_grid_selection_badges_targets_top_right_selection_marks():
    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def find_elements(self, by, value):
            return [
                FakeElement({"x": 116, "y": 136, "width": 17, "height": 17}),
                FakeElement({"x": 215, "y": 136, "width": 17, "height": 17}),
                FakeElement({"x": 13, "y": 205, "width": 18, "height": 17}),
                FakeElement({"x": 0, "y": 142, "width": 133, "height": 133}),
            ]

    badges = message_detail._find_photo_grid_selection_badges(FakeDriver())

    assert [element.rect for element in badges] == [
        {"x": 116, "y": 136, "width": 17, "height": 17},
        {"x": 215, "y": 136, "width": 17, "height": 17},
    ]


def test_note_submit_prefers_bottom_publish_button_region():
    taps = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def find_element(self, by, value):
            raise message_detail.NoSuchElementException()

        def find_elements(self, by, value):
            if "发布笔记" not in value:
                return []
            return [
                FakeElement({"x": 13, "y": 67, "width": 376, "height": 56}),
                FakeElement({"x": 145, "y": 781, "width": 244, "height": 47}),
            ]

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_submit(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 267.0, "y": 804.5})]


def test_find_bottom_submit_element_supports_android_text_attribute():
    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    header = FakeElement({"x": 434, "y": 191, "width": 212, "height": 66})
    bottom_button = FakeElement({"x": 639, "y": 2215, "width": 160, "height": 56})

    class FakeDriver:
        def get_window_size(self):
            return {"width": 1080, "height": 2400}

        def find_elements(self, by, value):
            if '@text="发布笔记"' in value:
                return [header, bottom_button]
            return []

    assert message_detail._find_bottom_submit_element(FakeDriver()) is bottom_button


def test_clear_existing_note_images_taps_scoped_remove_buttons_until_gone(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    groups = iter([
        [
            FakeElement({"x": 86, "y": 132, "width": 17, "height": 17}),
            FakeElement({"x": 185, "y": 132, "width": 17, "height": 17}),
        ],
        [FakeElement({"x": 86, "y": 132, "width": 17, "height": 17})],
        [FakeElement({"x": 86, "y": 132, "width": 17, "height": 17})],
        [],
    ])

    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda source: True)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "发布笔记 标题 正文")
    monkeypatch.setattr(message_detail, "_find_note_image_remove_buttons", lambda driver: next(groups, []))
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    message_detail._clear_existing_note_images(FakeDriver())

    assert taps == [
        ("mobile: tap", {"x": 193.5, "y": 140.5}),
        ("mobile: tap", {"x": 94.5, "y": 140.5}),
    ]


def test_tap_note_image_remove_button_falls_back_to_click_when_needed():
    events = []

    class FakeElement:
        rect = {"x": 86, "y": 132, "width": 17, "height": 17}

        def click(self):
            events.append("click")

    monkeypatch_driver = type("FakeDriver", (), {})()

    original = message_detail._tap_element_center
    try:
        message_detail._tap_element_center = lambda driver, element: False
        assert message_detail._tap_note_image_remove_button(monkeypatch_driver, FakeElement()) is True
    finally:
        message_detail._tap_element_center = original

    assert events == ["click"]


def test_find_note_image_remove_buttons_scopes_to_top_thumbnail_strip():
    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def find_elements(self, by, value):
            return [
                FakeElement({"x": 86, "y": 132, "width": 17, "height": 17}),
                FakeElement({"x": 185, "y": 132, "width": 17, "height": 17}),
                FakeElement({"x": 17, "y": 88, "width": 7, "height": 12}),
                FakeElement({"x": 118, "y": 207, "width": 6, "height": 13}),
                FakeElement({"x": 364, "y": 78, "width": 34, "height": 31}),
            ]

    buttons = message_detail._find_note_image_remove_buttons(FakeDriver())

    assert [element.rect for element in buttons] == [
        {"x": 86, "y": 132, "width": 17, "height": 17},
        {"x": 185, "y": 132, "width": 17, "height": 17},
    ]


def test_choose_note_location_option_taps_first_visible_chip(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, name, rect):
            self._name = name
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute in {"name", "label", "value"}:
                return self._name
            return None

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    driver = FakeDriver()
    elements = [
        FakeElement("西岸梦中心", {"x": 13, "y": 567, "width": 91, "height": 29}),
        FakeElement("长白山游客中心", {"x": 110, "y": 567, "width": 104, "height": 29}),
    ]

    monkeypatch.setattr(message_detail, "_find_visible_location_option_elements", lambda _driver: elements)
    assert message_detail._choose_note_location_option(driver, "长白山") is True
    assert taps == [("mobile: tap", {"x": 58.5, "y": 581.5})]


def test_choose_note_location_option_falls_back_to_first_visible_chip(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, name, rect):
            self._name = name
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute in {"name", "label", "value"}:
                return self._name
            return None

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    driver = FakeDriver()
    elements = [
        FakeElement("西岸梦中心", {"x": 13, "y": 567, "width": 91, "height": 29}),
        FakeElement("西岸美术馆", {"x": 110, "y": 567, "width": 91, "height": 29}),
    ]

    monkeypatch.setattr(message_detail, "_find_visible_location_option_elements", lambda _driver: elements)
    assert message_detail._choose_note_location_option(driver, "长白山") is True

    assert taps == [("mobile: tap", {"x": 58.5, "y": 581.5})]


def test_dismiss_editor_keyboard_prefers_done_without_coordinate_tap(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        message_detail,
        "_tap_editor_done",
        lambda driver: events.append("tap-editor-done") or True,
        raising=False,
    )
    monkeypatch.setattr(
        message_detail,
        "_wait_until",
        lambda predicate, timeout: events.append(("wait-keyboard-hidden", timeout)) or True,
    )
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda driver, text, timeout=1: False)

    class FakeDriver:
        def hide_keyboard(self, **kwargs):
            events.append(("hide-keyboard", kwargs))

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    message_detail._dismiss_editor_keyboard(FakeDriver())

    assert events == [
        "tap-editor-done",
        ("wait-keyboard-hidden", 3),
    ]


def test_dismiss_editor_keyboard_uses_native_fallback_without_coordinate_tap(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        message_detail,
        "_tap_editor_done",
        lambda driver: events.append("tap-editor-done") or False,
        raising=False,
    )
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda driver, text, timeout=1: False)

    class FakeDriver:
        def hide_keyboard(self, **kwargs):
            events.append(("hide-keyboard", kwargs))

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    message_detail._dismiss_editor_keyboard(FakeDriver())

    assert events == [
        "tap-editor-done",
        ("hide-keyboard", {}),
    ]


def test_tap_editor_done_targets_toolbar_control_center():
    events = []

    class FakeElement:
        rect = {"x": 341, "y": 460, "width": 48, "height": 34}

    class FakeDriver:
        def find_element(self, by, value):
            events.append(("find-element", by, value))
            return FakeElement()

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    assert message_detail._tap_editor_done(FakeDriver()) is True
    assert events == [
        (
            "find-element",
            message_detail.AppiumBy.XPATH,
            '//XCUIElementTypeOther[@visible="true" and (@name="完成" or @label="完成" or @value="完成")]',
        ),
        ("execute", "mobile: tap", {"x": 365.0, "y": 477.0}),
    ]


def test_keyboard_visible_requires_visible_keyboard_node():
    assert message_detail._keyboard_visible(
        '<XCUIElementTypeKeyboard type="XCUIElementTypeKeyboard" enabled="true" visible="true">'
    ) is True
    assert message_detail._keyboard_visible(
        '<XCUIElementTypeKeyboard type="XCUIElementTypeKeyboard" enabled="true" visible="false">'
    ) is False
    assert message_detail._keyboard_visible('<XCUIElementTypeOther visible="true">') is False


def test_prepare_note_location_section_rejects_visible_cropper(monkeypatch):
    events = []

    monkeypatch.setattr(
        message_detail,
        "_dismiss_editor_keyboard",
        lambda driver: events.append("dismiss-keyboard"),
    )
    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: 'name="裁剪图片" label="裁剪图片" enabled="true" visible="true"',
    )
    monkeypatch.setattr(
        message_detail,
        "swipe_vertical",
        lambda driver, direction="up": events.append(("swipe", direction)),
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    with pytest.raises(AssertionError, match="cropper"):
        message_detail._prepare_note_location_section(object())

    assert events == ["dismiss-keyboard"]


def test_fill_note_location_opens_picker_from_unselected_row(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail, "_prepare_note_location_section", lambda driver: events.append("prepared"))
    monkeypatch.setattr(
        message_detail,
        "_tap_text_or_contains",
        lambda driver, text: events.append(("tap", text)) or text == "不标记地点",
    )
    monkeypatch.setattr(
        message_detail,
        "_choose_note_location_option",
        lambda driver, location: events.append(("choose", location)) or True,
    )

    message_detail._fill_note_location(object(), "长白山")

    assert events == [
        "prepared",
        ("tap", "不标记地点"),
        ("choose", "长白山"),
    ]


def test_choose_note_location_option_searches_requested_location_from_picker(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self):
            self.values = []

        def click(self):
            events.append("click-search-input")

        def clear(self):
            events.append("clear-search-input")

        def send_keys(self, value):
            self.values.append(value)
            events.append(("type-search-input", value))

    class FakeDriver:
        def __init__(self):
            self.search_input = FakeElement()

        def find_element(self, by, value):
            events.append(("find-element", by, value))
            if "搜索地点" in value:
                return self.search_input
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_location_picker_visible", lambda source: True)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "搜索地点")
    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: events.append(("tap-text", text)) or text == "搜索")
    monkeypatch.setattr(
        message_detail,
        "_choose_first_valid_location_from_picker",
        lambda driver: events.append("choose-first-location") or True,
    )

    assert message_detail._choose_note_location_option(FakeDriver(), "长白山") is True
    assert events == [
        (
            "find-element",
            message_detail.AppiumBy.XPATH,
            '//android.widget.EditText[contains(@hint, "搜索地点") or contains(@text, "搜索地点")]',
        ),
        "click-search-input",
        "clear-search-input",
        ("type-search-input", "长白山"),
        "hide-keyboard",
        ("tap-text", "搜索"),
        "choose-first-location",
    ]


def test_choose_first_valid_location_from_picker_prefers_first_result_row(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, name, rect):
            self._name = name
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute in {"name", "label", "value"}:
                return self._name
            return None

    class FakeDriver:
        def find_elements(self, by, value):
            return [
                FakeElement("不标记地点", {"x": 13, "y": 451, "width": 376, "height": 57}),
                FakeElement("黑龙江炒货 上海市上海市杨浦区三门路316-2号", {"x": 13, "y": 521, "width": 376, "height": 90}),
                FakeElement("黑龙江炒货(泰禾红御店) 上海市上海市宝山区恒高路83弄1-121号", {"x": 13, "y": 611, "width": 376, "height": 70}),
                FakeElement("没有找到匹配地点，换个关键词试试", {"x": 13, "y": 765, "width": 376, "height": 46}),
            ]

    monkeypatch.setattr(
        message_detail,
        "_tap_element_center",
        lambda driver, element: taps.append(element.rect) or True,
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout=5: True)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "done")

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert taps == [{"x": 13, "y": 521, "width": 376, "height": 90}]


def test_choose_first_valid_location_from_picker_accepts_real_device_result_geometry(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, name, rect):
            self._name = name
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute in {"name", "label", "value"}:
                return self._name
            return None

    result_row = FakeElement(
        "洱海公园 云南省大理白族自治州大理市洱河南路1号",
        {"x": 52, "y": 175, "width": 350, "height": 71},
    )

    class FakeDriver:
        def find_elements(self, by, value):
            return [
                FakeElement(
                    "洱海公园 洱海 洱海大游船 洱海国际生态城",
                    {"x": 52, "y": 175, "width": 350, "height": 1615},
                ),
                result_row,
            ]

    monkeypatch.setattr(
        message_detail,
        "_tap_element_center",
        lambda driver, element: taps.append(element) or True,
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout=5: True)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "done")

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert taps == [result_row]


def test_find_location_results_supports_android_text_rows():
    class FakeElement:
        def __init__(self, text, rect):
            self._text = text
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute == "text":
                return self._text
            return None

    result = FakeElement(
        "洱海公园",
        {"x": 68, "y": 1512, "width": 860, "height": 56},
    )

    class FakeDriver:
        def find_elements(self, by, value):
            if value == "//android.widget.TextView":
                return [
                    FakeElement("标记地点", {"x": 34, "y": 1003, "width": 1012, "height": 71}),
                    FakeElement("不标记地点", {"x": 68, "y": 1339, "width": 855, "height": 56}),
                    result,
                ]
            return []

    assert message_detail._find_location_result_elements(FakeDriver()) == [result]


def test_choose_android_location_taps_visible_row_area_above_keyboard(monkeypatch):
    taps = []

    class FakeElement:
        rect = {"x": 68, "y": 1512, "width": 860, "height": 56}

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_find_location_result_elements", lambda driver: [FakeElement()])
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 498.0, "y": 1492.0})]


def test_choose_android_location_refinds_and_taps_row_center_after_keyboard_closes(monkeypatch):
    first_result = object()
    refreshed_result = object()
    result_batches = iter([[first_result], [refreshed_result]])
    waits = iter([False, True])
    visible_area_taps = []
    center_taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        message_detail,
        "_find_location_result_elements",
        lambda driver: next(result_batches),
    )
    monkeypatch.setattr(
        message_detail,
        "_tap_location_result",
        lambda driver, element: visible_area_taps.append(element) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_tap_element_center",
        lambda driver, element: center_taps.append(element) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_wait_until",
        lambda predicate, timeout: next(waits),
    )

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert visible_area_taps == [first_result]
    assert center_taps == [refreshed_result]


def test_location_picker_visible_ignores_collapsed_unselected_row():
    page_source = 'name="不标记地点" label="不标记地点" enabled="true" visible="true"'

    assert message_detail._location_picker_visible(page_source) is False


def test_location_picker_visible_accepts_android_search_input():
    page_source = '<android.widget.EditText text="搜索地点" hint="搜索地点" />'

    assert message_detail._location_picker_visible(page_source) is True


def test_find_location_search_input_supports_android_hint():
    expected = object()

    class FakeDriver:
        def find_element(self, by, value):
            if value == '//android.widget.EditText[contains(@hint, "搜索地点") or contains(@text, "搜索地点")]':
                return expected
            raise message_detail.NoSuchElementException()

    assert message_detail._find_location_search_input(FakeDriver()) is expected


def test_search_note_location_keeps_android_picker_open(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def send_keys(self, value):
            events.append(("type", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(message_detail, "_find_location_search_input", lambda driver: FakeElement())
    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(
        message_detail,
        "_tap_text_or_contains",
        lambda driver, text: events.append(("tap-text", text)) or False,
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._search_note_location_from_picker(FakeDriver(), "云南洱海") is True
    assert events == ["click", "clear", ("type", "云南洱海")]


def test_fill_note_location_skips_when_configured_to_not_mark_location(monkeypatch):
    events = []

    monkeypatch.setattr(message_detail, "_prepare_note_location_section", lambda driver: events.append("prepared"))
    monkeypatch.setattr(
        message_detail,
        "_tap_text_or_contains",
        lambda driver, text: events.append(("tap", text)) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_choose_note_location_option",
        lambda driver, location: events.append(("choose", location)) or True,
    )

    message_detail._fill_note_location(object(), "不标记地点")

    assert events == []
