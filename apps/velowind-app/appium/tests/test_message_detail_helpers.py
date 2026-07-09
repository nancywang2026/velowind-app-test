from velowind_appium.modules import message_detail
from velowind_appium.modules.message_detail import (
    build_changbaishan_note_draft,
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


def test_build_changbaishan_note_draft_uses_requested_content():
    draft = build_changbaishan_note_draft()

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert "第一次去长白山" in draft.body
    assert draft.topics == ["#长白山", "#旅行日记", "#治愈系风景", "#长白山天池", "#东北旅行"]
    assert draft.location == "长白山"
    assert draft.allow_comments is True


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
    monkeypatch.setattr(message_detail, "_upload_note_image", lambda driver: events.append("upload-image"))
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
        "upload-image",
        ("title", draft.title),
        ("body", draft.body),
        ("body-topics", draft.topics),
        ("location", draft.location),
        ("allow-comments", True),
    ]


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
    monkeypatch.setattr(message_detail, "_tap_note_image_plus", lambda driver: True)
    monkeypatch.setattr(message_detail, "_choose_photo_library_source", lambda driver: True)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_photo_library_visible", lambda driver, timeout=5: False, raising=False)

    try:
        message_detail._upload_note_image(object())
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

    assert message_detail._choose_local_photo(FakeDriver()) is True
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

    assert message_detail._choose_local_photo(FakeDriver()) is True
    assert events == ["pick-photo", "picker-done"]


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
