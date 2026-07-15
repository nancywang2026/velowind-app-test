from velowind_appium.modules import message_detail
from pathlib import Path
from selenium.common.exceptions import StaleElementReferenceException

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


def test_parse_detail_snapshot_extracts_named_user_bottom_action_counts():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="Nancy 3 2 5" label="Nancy 3 2 5" />
    </AppiumAUT>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.bottom_action_counts == ["3", "2", "5"]


def test_note_search_results_visible_accepts_type_matching_card_without_interaction_labels():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="骑行" />
      <XCUIElementTypeOther name="【API复测】沿途有风 0714-1205 #骑行 用户 admin 3" />
    </AppiumAUT>
    """

    assert message_detail._note_search_results_visible(page_source, "骑行") is True


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
        ("find-element", message_detail.AppiumBy.XPATH, '//*[@name="搜索地点" or @label="搜索地点" or @value="搜索地点"]'),
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


def test_find_location_result_elements_skips_stale_candidates():
    class StaleElement:
        def get_attribute(self, attribute):
            return "stale result"

        @property
        def rect(self):
            raise StaleElementReferenceException()

    class ValidElement:
        def __init__(self):
            self.rect = {"x": 52, "y": 175, "width": 350, "height": 71}

        def get_attribute(self, attribute):
            if attribute in {"name", "label", "value"}:
                return "长白山国家级自然保护区(暂停开放) 吉林省延边朝鲜族自治州安图县"
            return None

    valid_element = ValidElement()

    class FakeDriver:
        def find_elements(self, by, value):
            if "XCUIElementTypeOther" in value:
                return [StaleElement(), valid_element]
            return []

    assert message_detail._find_location_result_elements(FakeDriver()) == [valid_element]


def test_location_picker_visible_ignores_collapsed_unselected_row():
    page_source = 'name="不标记地点" label="不标记地点" enabled="true" visible="true"'

    assert message_detail._location_picker_visible(page_source) is False


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
