from velowind_appium.modules import message_detail
from pathlib import Path

from velowind_appium.modules.message_detail import (
    build_changbaishan_note_draft,
    list_message_note_use_case_ids,
    load_message_note_draft,
    message_note_form_is_visible,
    message_note_publish_error_signal,
    message_note_publish_success_signal,
    parse_detail_snapshot,
)

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
    assert draft.location == "长白山"
    assert draft.album == "长白山"
    assert draft.allow_comments is True


def test_load_message_note_draft_reads_yaml_use_case():
    testdata_path = (
        Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
    )

    draft = load_message_note_draft("publish-note-changbaishan", testdata_path=testdata_path)

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert draft.album == "长白山"
    assert draft.location == "长白山"


def test_list_message_note_use_case_ids_reads_all_yaml_cases():
    testdata_path = (
        Path(__file__).resolve().parent / "message" / "testdata" / "publish_notes.yaml"
    )

    use_case_ids = list_message_note_use_case_ids(testdata_path=testdata_path)

    assert "publish-note-changbaishan" in use_case_ids
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


def test_upload_note_image_reports_when_photo_library_does_not_open(monkeypatch):
    draft = build_changbaishan_note_draft()
    monkeypatch.setattr(message_detail, "_tap_note_image_plus", lambda driver: True)
    monkeypatch.setattr(message_detail, "_choose_photo_library_source", lambda driver: True)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_photo_library_visible", lambda driver, timeout=5: False, raising=False)

    try:
        message_detail._upload_note_image(object(), draft)
    except AssertionError as error:
        assert "Photo library did not open" in str(error)
    else:
        raise AssertionError("Expected upload to fail when the photo library does not open")


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
        def click(self):
            events.append("pick-photo")

    class FakeDriver:
        def find_element(self, by, value):
            if value == "(//XCUIElementTypeCell)[1]":
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: events.append("confirm-cropper") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=1, album_name=None) is True
    assert events == ["pick-photo", "confirm-cropper"]


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


def test_choose_local_photo_taps_picker_done_when_system_picker_stays_open(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("pick-photo")

    class FakeDriver:
        def find_element(self, by, value):
            if value == "(//XCUIElementTypeCell)[1]":
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: False)
    monkeypatch.setattr(message_detail, "_confirm_system_photo_picker_selection", lambda driver, timeout=10: events.append("picker-done") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=1, album_name=None) is True
    assert events == ["pick-photo", "picker-done"]


def test_choose_local_photo_prefers_requested_picture_index(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("pick-photo")

    class FakeDriver:
        def find_element(self, by, value):
            if value == "(//XCUIElementTypeCell)[3]":
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=3, album_name=None) is True
    assert events == ["pick-photo"]


def test_choose_local_photo_opens_requested_album_first(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self, name):
            self.name = name

        def click(self):
            events.append(("pick-photo", self.name))

    class FakeDriver:
        def find_element(self, by, value):
            if value == "(//XCUIElementTypeCell)[1]":
                return FakeElement("photo-1")
            if value == "(//XCUIElementTypeCell)[2]":
                return FakeElement("photo-2")
            if value == "(//XCUIElementTypeCell)[3]":
                return FakeElement("photo-3")
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_open_photo_album", lambda driver, album_name: events.append(("open-album", album_name)) or True)
    monkeypatch.setattr(message_detail, "_confirm_note_image_cropper", lambda driver, timeout=10: False)
    monkeypatch.setattr(message_detail, "_confirm_system_photo_picker_selection", lambda driver, timeout=10: events.append("picker-done") or True)

    assert message_detail._choose_local_photo(FakeDriver(), picture_index=2, album_name="长白山") is True
    assert events == [
        ("open-album", "长白山"),
        ("pick-photo", "photo-1"),
        ("pick-photo", "photo-2"),
        ("pick-photo", "photo-3"),
        "picker-done",
    ]


def test_open_photo_album_switches_to_collections_before_tapping_album(monkeypatch):
    events = []

    monkeypatch.setattr(
        message_detail,
        "_tap_text_or_contains",
        lambda driver, text: events.append(("tap-text", text)) or text == "精选集",
    )
    monkeypatch.setattr(
        message_detail,
        "_tap_named_element_center",
        lambda driver, text: events.append(("tap-album", text)) or text == "云南洱海",
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._open_photo_album(object(), "云南洱海") is True
    assert events == [("tap-text", "精选集"), ("tap-album", "云南洱海")]


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
