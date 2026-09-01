from velowind_appium.modules import message_detail
from velowind_appium import reporting
from pathlib import Path
from io import BytesIO
import pytest
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from PIL import Image

from velowind_appium.modules.message_detail import (
    MessageNoteDraft,
    build_changbaishan_note_draft,
    list_message_note_use_case_ids,
    load_message_note_draft,
    message_note_form_is_visible,
    message_note_publish_error_signal,
    message_note_publish_success_signal,
    parse_detail_snapshot,
)


def test_publish_message_note_validates_video_only_when_media_type_is_video(monkeypatch, tmp_path: Path):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video")
    calls = []

    monkeypatch.setattr(message_detail, "open_message_note_publisher", lambda *args, **kwargs: None)
    monkeypatch.setattr(message_detail, "fill_message_note_form", lambda *args, **kwargs: None)
    monkeypatch.setattr(message_detail, "submit_message_note", lambda *args, **kwargs: "视频上传中")
    monkeypatch.setattr(message_detail, "wait_for_video_upload_completion", lambda *args, **kwargs: "视频上传完成")
    monkeypatch.setattr(
        message_detail,
        "_validate_published_note_video_matches_source",
        lambda driver, source_path, **kwargs: calls.append(Path(source_path)),
    )
    monkeypatch.setattr(
        message_detail,
        "_validate_published_note_image_matches_uploaded_preview",
        lambda *args, **kwargs: calls.append("image"),
    )

    video_draft = MessageNoteDraft(title="视频", body="正文", topics=[], location="", media_type="video")
    image_draft = MessageNoteDraft(title="图片", body="正文", topics=[], location="", media_type="image")
    video_without_source_draft = MessageNoteDraft(title="无源视频", body="正文", topics=[], location="", media_type="video")

    message_detail.publish_message_note(object(), video_draft, video_source_path=source_video)
    message_detail.publish_message_note(object(), image_draft)
    message_detail.publish_message_note(object(), video_without_source_draft)

    assert calls == [source_video, "image"]


def test_publish_message_note_forwards_observed_video_progress_signal(monkeypatch, tmp_path: Path):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video")
    observed_signals = []

    monkeypatch.setattr(message_detail, "open_message_note_publisher", lambda *args, **kwargs: None)
    monkeypatch.setattr(message_detail, "fill_message_note_form", lambda *args, **kwargs: None)
    monkeypatch.setattr(message_detail, "submit_message_note", lambda *args, **kwargs: "视频上传中")
    monkeypatch.setattr(
        message_detail,
        "wait_for_video_upload_completion",
        lambda *args, **kwargs: observed_signals.append(kwargs.get("observed_signal")) or "视频上传中",
    )
    monkeypatch.setattr(
        message_detail,
        "_validate_published_note_video_matches_source",
        lambda *args, **kwargs: None,
    )

    draft = MessageNoteDraft(title="视频", body="正文", topics=[], location="", media_type="video")

    assert message_detail.publish_message_note(object(), draft, video_source_path=source_video) == "视频上传中"
    assert observed_signals == ["视频上传中"]


def test_load_message_note_draft_reads_video_media_source(tmp_path: Path):
    testdata = tmp_path / "publish_notes.yaml"
    testdata.write_text(
        """
use_cases:
  - id: publish-note-video-camera
    note:
      title: 标题
      body: 正文
      media_type: video
      media_source: camera
""",
        encoding="utf-8",
    )

    draft = message_detail.load_message_note_draft("publish-note-video-camera", testdata_path=testdata)

    assert draft.media_type == "video"
    assert draft.media_source == "camera"


def test_android_note_search_coordinate_targets_visible_header_icon(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(message_detail, "_note_search_visible", lambda page_source: page_source == "search-visible")
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "search-visible")

    assert message_detail._tap_note_search_entry_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 1004, "y": 160})]


def test_publish_note_image_validation_records_selected_album_source(monkeypatch, tmp_path):
    media_dir = tmp_path / "media"
    album_dir = media_dir / "图片"
    album_dir.mkdir(parents=True)
    source_path = album_dir / "1.jpg"
    source_path.write_bytes(b"original-photo")
    artifact_dir = tmp_path / "artifacts"
    draft = MessageNoteDraft(title="标题", body="正文", topics=[], location="", album="图片", picture_index=1)

    class FakeDriver:
        pass

    class FakeConfig:
        login_username = "user"
        login_password = "pass"

    class FakeConfig:
        login_username = "user"
        login_password = "pass"

    class FakeConfig:
        login_username = "user"
        login_password = "pass"

    monkeypatch.setenv("VW_ANDROID_MEDIA_DIR", str(media_dir))
    monkeypatch.setenv("VW_APPIUM_ARTIFACT_DIR", str(artifact_dir))
    driver = FakeDriver()

    message_detail._record_note_selected_album_image_source(driver, draft)

    copied_path = getattr(driver, "_publish_note_album_source_image_path")
    assert copied_path.read_bytes() == b"original-photo"
    assert copied_path.parent == artifact_dir
    assert "图片-index-1" in copied_path.name
    assert getattr(driver, "_publish_note_album_source_position") == "album=图片 index=1 source=1.jpg"


def test_publish_note_image_validation_uses_album_source_path(monkeypatch, tmp_path):
    source_path = tmp_path / "album-source.jpg"
    source_path.write_bytes(b"source")
    actual_path = tmp_path / "detail.png"
    compared_paths = []

    class FakeResult:
        is_valid = True

    class FakeImage:
        size = (320, 240)

        def save(self, path):
            actual_path.write_bytes(b"actual")

    class FakeDriver:
        _publish_note_album_source_image_path = source_path

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "<hierarchy />")
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(message_detail, "find_note_detail_image_bounds", lambda page_source: object())
    monkeypatch.setattr(message_detail, "_capture_image_bounds", lambda driver, bounds: FakeImage())
    monkeypatch.setattr(message_detail, "_publish_note_validation_detail_path", lambda: actual_path)
    monkeypatch.setattr(
        message_detail,
        "compare_images_for_publish_note",
        lambda source, actual: compared_paths.append((source, actual)) or FakeResult(),
    )

    message_detail._validate_published_note_image_matches_uploaded_preview(FakeDriver())

    assert compared_paths == [(source_path, actual_path)]


def test_publish_note_image_validation_artifacts_are_attached_to_allure(monkeypatch, tmp_path):
    from PIL import Image

    source_path = tmp_path / "source.png"
    detail_path = tmp_path / "detail.png"
    artifact_dir = tmp_path / "artifacts"
    Image.new("RGB", (10, 10), "red").save(source_path)
    Image.new("RGB", (10, 10), "blue").save(detail_path)
    attached = []

    class FakeResult:
        is_valid = False
        source_size = (10, 10)
        actual_size = (10, 10)
        aspect_ratio_delta = 0
        mean_pixel_delta = 255
        reason = "pixel-delta-too-high"

        def __str__(self):
            return "fake comparison"

    monkeypatch.setattr(message_detail, "_publish_note_artifact_dir", lambda: artifact_dir)
    monkeypatch.setattr(
        message_detail,
        "attach_file_if_present",
        lambda path, *, name=None, attachment_type=None: attached.append((Path(path).name, name, attachment_type)),
        raising=False,
    )
    monkeypatch.setattr(message_detail.time, "time", lambda: 123)
    attachment_type = reporting.allure.attachment_type

    message_detail._save_publish_note_image_validation_artifacts(source_path, detail_path, FakeResult())

    assert attached == [
        ("source.png", "publish-note-image-validation-source.png", attachment_type.PNG),
        ("detail.png", "publish-note-image-validation-detail.png", attachment_type.PNG),
        ("publish-note-image-validation-123-diff.png", "publish-note-image-validation-diff.png", attachment_type.PNG),
        ("publish-note-image-validation-123.txt", "publish-note-image-validation.txt", attachment_type.TEXT),
    ]


def test_publish_note_image_validation_opens_detail_image_before_capture(monkeypatch, tmp_path):
    source_path = tmp_path / "album-source.jpg"
    source_path.write_bytes(b"source")
    actual_path = tmp_path / "detail.png"
    events = []

    class FakeResult:
        is_valid = True

    class FakeImage:
        def save(self, path):
            actual_path.write_bytes(b"actual")

    class FakeDriver:
        _publish_note_album_source_image_path = source_path

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "<hierarchy />")
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(message_detail, "find_note_detail_image_bounds", lambda page_source: "detail-bounds")
    monkeypatch.setattr(
        message_detail,
        "_open_published_note_image_viewer",
        lambda driver, bounds, timeout: events.append(("open-viewer", bounds, timeout)) or "viewer-bounds",
    )
    monkeypatch.setattr(
        message_detail,
        "_capture_image_bounds",
        lambda driver, bounds: events.append(("capture", bounds)) or FakeImage(),
    )
    monkeypatch.setattr(message_detail, "_publish_note_validation_detail_path", lambda: actual_path)
    monkeypatch.setattr(message_detail, "compare_images_for_publish_note", lambda source, actual: FakeResult())

    message_detail._validate_published_note_image_matches_uploaded_preview(FakeDriver(), timeout=12)

    assert events == [("open-viewer", "detail-bounds", 12), ("capture", "viewer-bounds")]


def test_publish_note_image_validation_opens_my_notes_detail_by_title_before_capture(monkeypatch, tmp_path):
    source_path = tmp_path / "album-source.jpg"
    source_path.write_bytes(b"source")
    actual_path = tmp_path / "detail.png"
    events = []

    class FakeResult:
        is_valid = True

    class FakeImage:
        def save(self, path):
            actual_path.write_bytes(b"actual")

    class FakeDriver:
        _publish_note_album_source_image_path = source_path

    monkeypatch.setattr(message_detail, "message_detail_is_visible", lambda driver: False)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "我的笔记 测试标题 发布")
    monkeypatch.setattr(
        message_detail,
        "_open_published_note_detail_from_my_notes",
        lambda driver, title, timeout=20: events.append(("open-my-notes", title, timeout)),
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
    monkeypatch.setattr(message_detail, "find_note_detail_image_bounds", lambda page_source: "detail-bounds")
    monkeypatch.setattr(message_detail, "_open_published_note_image_viewer", lambda driver, bounds, timeout: bounds)
    monkeypatch.setattr(
        message_detail,
        "_capture_image_bounds",
        lambda driver, bounds: events.append(("capture", bounds)) or FakeImage(),
    )
    monkeypatch.setattr(message_detail, "_publish_note_validation_detail_path", lambda: actual_path)
    monkeypatch.setattr(message_detail, "compare_images_for_publish_note", lambda source, actual: FakeResult())

    message_detail._validate_published_note_image_matches_uploaded_preview(FakeDriver(), title="测试标题")

    assert events == [("open-my-notes", "测试标题", 20), ("capture", "detail-bounds")]


def test_my_notes_list_visible_accepts_android_notes_tabs():
    assert message_detail._my_notes_list_visible("我的笔记 笔记 收藏 点赞") is True


def test_android_published_note_title_accepts_truncated_prefix(monkeypatch):
    taps = []

    class FakeElement:
        rect = {"x": 62, "y": 1489, "width": 552, "height": 130}

        def get_attribute(self, name):
            return "测试 - 长白山真的有种让人瞬间安静下来" if name == "text" else None

    class FakeDriver:
        def find_elements(self, by, value):
            return [FakeElement()]

    monkeypatch.setattr(
        message_detail,
        "_adb_input_tap",
        lambda driver, x, y: taps.append((x, y)) or True,
    )

    assert message_detail._tap_android_published_note_title_prefix(
        FakeDriver(),
        "测试 - 长白山真的有种让人瞬间安静下来的魔力",
    ) is True
    assert taps == [(338, 1554)]


def test_tap_published_note_title_uses_visible_ios_title_rect_when_xpath_is_unavailable(monkeypatch):
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="我的笔记 笔记 收藏 点赞" visible="true" x="0" y="0" width="402" height="874">
        <XCUIElementTypeStaticText
          name="测试 - 长白山真的有种让人瞬间安静下来"
          label="测试 - 长白山真的有种让人瞬间安静下来"
          visible="true"
          enabled="true"
          accessible="true"
          x="13"
          y="670"
          width="376"
          height="61"
        />
      </XCUIElementTypeOther>
    </AppiumAUT>
    """
    taps = []

    class FakeElement:
        def click(self):
            raise message_detail.NoSuchElementException()

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_element(self, *_args, **_kwargs):
            raise message_detail.NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: False)

    assert message_detail._tap_published_note_title(
        FakeDriver(),
        "测试 - 长白山真的有种让人瞬间安静下来的魔力",
        page_source=page_source,
    ) is True
    assert taps == [("mobile: tap", {"x": 201.0, "y": 700.5})]


def test_ios_note_search_entry_coordinate_defers_visibility_wait(monkeypatch):
    calls = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(
        message_detail,
        "_tap_note_search_entry_by_coordinate",
        lambda driver: calls.append("coordinate") or True,
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: calls.append("wait") or True)

    assert message_detail._tap_note_search_entry(FakeDriver()) is True
    assert calls == ["coordinate"]


def test_android_note_search_submit_targets_visible_header_action(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_android_search_request_started", lambda page_source: page_source == "request-started")
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "request-started")

    assert message_detail._tap_note_search_submit_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 972, "y": 175})]


def test_android_publish_entry_coordinate_targets_bottom_center_plus_button(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1440, "height": 2560}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout: True)

    assert message_detail._tap_publish_entry_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 720, "y": 2393})]


def test_capture_published_note_video_frames_uses_screenshots_without_appium_recording(monkeypatch):
    screenshot = BytesIO()
    Image.new("RGB", (402, 874), "red").save(screenshot, format="PNG")
    calls = []

    class FakeDriver:
        def start_recording_screen(self, **_kwargs):
            raise AssertionError("system ffmpeg recording must not be used")

        def get_screenshot_as_png(self):
            calls.append("screenshot")
            return screenshot.getvalue()

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            calls.append((script, payload))

    monkeypatch.setattr(message_detail.time, "sleep", lambda _seconds: None)
    frames, paths = message_detail._capture_published_note_video_frames(
        FakeDriver(),
        type("Bounds", (), {"x": 0, "y": 122, "width": 402, "height": 536})(),
        sample_count=2,
        seconds=0,
    )

    assert len(frames) == 2
    assert len(paths) == 2
    assert calls.count("screenshot") == 2
    assert not any(isinstance(call, tuple) and call[0] == "mobile: tap" for call in calls)


def test_validate_published_note_video_waits_for_loading_to_clear_before_sampling(monkeypatch, tmp_path):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video")
    frame_path = tmp_path / "frame.png"
    Image.new("RGB", (10, 10), "red").save(frame_path)
    current = {"loading": False}
    page_states = iter(["loading", "ready", "ready"])

    def page_source_for_state(state: str) -> str:
        loading_nodes = """
            <XCUIElementTypeOther name="post-detail-video-loading" label="正在缓冲视频..."
                x="0" y="162" width="402" height="40" visible="true" />
            <XCUIElementTypeStaticText name="正在缓冲视频..." label="正在缓冲视频..." />
        """ if state == "loading" else ""
        return f"""
        <AppiumAUT>
          <XCUIElementTypeOther name="post-detail-page" label="写留言 评论">
            <XCUIElementTypeOther name="post-detail-video-surface"
              x="0" y="122" width="402" height="665" visible="true" />
            {loading_nodes}
          </XCUIElementTypeOther>
        </AppiumAUT>
        """

    def fake_page_source(_driver):
        state = next(page_states, "ready")
        current["loading"] = state == "loading"
        return page_source_for_state(state)

    def fake_capture(_driver, _bounds):
        assert not current["loading"], "video frames should be sampled after buffering clears"
        return [Image.new("RGB", (10, 10), "red")], [frame_path]

    monkeypatch.setattr(message_detail, "message_detail_is_visible", lambda _driver: True)
    monkeypatch.setattr(message_detail, "_safe_page_source", fake_page_source)
    monkeypatch.setattr(message_detail, "_capture_published_note_video_frames", fake_capture)
    monkeypatch.setattr(message_detail, "compare_video_to_frames", lambda *args, **kwargs: type("Result", (), {"is_valid": True})())
    monkeypatch.setattr(message_detail, "_publish_note_video_validation_summary_path", lambda: tmp_path / "summary.txt")
    monkeypatch.setattr(message_detail, "attach_file_if_present", lambda *args, **kwargs: None)
    monkeypatch.setattr(message_detail.time, "sleep", lambda _seconds: None)

    message_detail._validate_published_note_video_matches_source(object(), source_path=source_video, timeout=2)


def test_android_publish_entry_coordinate_targets_pixel_10_plus_button(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1280, "height": 2856}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout: True)

    assert message_detail._tap_publish_entry_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 640, "y": 2670})]


def test_ios_publish_entry_coordinate_targets_visible_bottom_center_plus_button(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @staticmethod
        def get_window_rect():
            return {"width": 402, "height": 874}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout: True)

    assert message_detail._tap_publish_entry_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 201, "y": 751})]


def test_open_message_note_publisher_recovers_from_login_page_before_business_step(monkeypatch):
    page = {"source": "手机号登录 请输入手机号 密码登录 验证并登录"}
    calls = []

    class FakeDriver:
        pass

    class FakeConfig:
        login_username = "user"
        login_password = "pass"

    def recover_publish_entry(driver, ios_config):
        calls.append("recover-login")
        page["source"] = "发布表单"
        return True

    monkeypatch.setattr(message_detail, "ensure_logged_in_if_needed", recover_publish_entry)
    monkeypatch.setattr(message_detail, "_prepare_android_publish_entry", lambda driver: None)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: page["source"])
    monkeypatch.setattr(message_detail, "_publish_sheet_visible", lambda page_source: False)
    monkeypatch.setattr(message_detail, "_tap_publish_entry_if_present", lambda driver: False)
    monkeypatch.setattr(message_detail, "_tap_note_type_if_present", lambda driver: False)
    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda page_source: page_source == "发布表单")

    message_detail.open_message_note_publisher(FakeDriver(), ios_config=FakeConfig(), timeout=1)

    assert calls == ["recover-login"]


def test_open_message_note_publisher_recovers_when_publish_tap_opens_login_page(monkeypatch):
    clock = {"now": 0.0}
    page = {"source": "首页 笔记 活动 消息 我的 全国 推荐"}
    calls = []

    class FakeDriver:
        pass

    class FakeConfig:
        login_username = "user"
        login_password = "pass"

    def tap_publish_entry(driver):
        page["source"] = "手机号登录 请输入手机号 密码登录 验证并登录"
        return True

    def wait_for_form(condition, timeout):
        return True

    def recover_login(driver, ios_config):
        calls.append("recover-login")
        page["source"] = "发布表单"
        return True

    monkeypatch.setattr(message_detail.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(message_detail, "ensure_logged_in_if_needed", recover_login)
    monkeypatch.setattr(message_detail, "_prepare_android_publish_entry", lambda driver: None)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: page["source"])
    monkeypatch.setattr(message_detail, "_publish_sheet_visible", lambda page_source: False)
    monkeypatch.setattr(message_detail, "_tap_publish_entry_if_present", tap_publish_entry)
    monkeypatch.setattr(message_detail, "_tap_note_type_if_present", lambda driver: False)
    monkeypatch.setattr(message_detail, "_wait_until", wait_for_form)
    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda page_source: page_source == "发布表单")

    message_detail.open_message_note_publisher(FakeDriver(), ios_config=FakeConfig(), timeout=20)

    assert calls == ["recover-login"]


def test_find_note_search_input_supports_android_edit_text():
    expected = object()

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def find_element(by, value):
            if value == '//android.widget.EditText[contains(@hint, "请输入内容")]':
                return expected
            raise NoSuchElementException("no match")

    assert message_detail._find_note_search_input(FakeDriver(), timeout=0.1) is expected


def test_find_note_search_input_prefers_ios_class_chain():
    expected = object()
    calls = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @staticmethod
        def find_element(by, value):
            calls.append((by, value))
            if by == message_detail.AppiumBy.IOS_CLASS_CHAIN:
                return expected
            raise NoSuchElementException("no match")

    assert message_detail._find_note_search_input(FakeDriver(), timeout=0.1) is expected
    assert calls == [
        (message_detail.AppiumBy.IOS_CLASS_CHAIN, "**/XCUIElementTypeSearchField"),
    ]


def test_android_note_search_results_accept_hidden_keyword_matches():
    page_source = """
    <hierarchy>
      <android.widget.EditText text="骑行" hint="请输入内容" bounds="[54,160][1026,240]" />
      <android.widget.ImageView resource-id="image" bounds="[36,422][504,998]" />
      <android.widget.TextView text="想去一趟洱海，想顺便把自己也放空一下" bounds="[64,1020][468,1098]" />
      <android.widget.TextView text="#云南洱海" bounds="[64,1110][280,1160]" />
      <android.widget.TextView text="用户 15aa909316f54c2b8671dc3c35476559" bounds="[64,1180][548,1234]" />
    </hierarchy>
    """

    assert message_detail._note_search_results_visible(page_source, "骑行") is True


def test_tap_note_search_result_tries_next_card_when_first_does_not_open(monkeypatch):
    events = []
    state = {"page": "search-results"}

    class FakeDriver:
        def find_element(self, by, value):
            raise message_detail.NoSuchElementException("missing")

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(
        message_detail,
        "tap_first_note_card",
        lambda driver, page_source, verify_open, timeout=1.2: events.append(page_source) or page_source == "page-2",
    )
    monkeypatch.setattr(message_detail, "_tap_accessibility_id_now", lambda driver, value: False)
    monkeypatch.setattr(message_detail, "_tap_first_visible_note_search_result", lambda driver, **kwargs: False)
    monkeypatch.setattr(message_detail, "_tap_first_note_search_result_by_coordinate", lambda driver: False)
    monkeypatch.setattr(
        message_detail,
        "swipe_vertical",
        lambda driver, direction="up": events.append(("swipe", direction)) or state.update(page="page-2"),
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._tap_first_note_search_result(FakeDriver()) is True
    assert events == ["search-results", ("swipe", "up"), "page-2"]


def test_tap_note_search_result_prefers_visible_result_fast_path(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "search-results")
    monkeypatch.setattr(
        message_detail,
        "_tap_first_visible_note_search_result",
        lambda driver, **kwargs: events.append("visible-result") or True,
    )
    monkeypatch.setattr(
        message_detail,
        "tap_first_note_card",
        lambda *args, **kwargs: events.append("generic-card") or True,
    )

    assert message_detail._tap_first_note_search_result(FakeDriver()) is True
    assert events == ["visible-result"]


def test_click_note_search_result_title_prefers_ios_predicate(monkeypatch):
    calls = []

    class FakeElement:
        def click(self):
            calls.append(("click",))

    class FakeDriver:
        def find_element(self, by, value):
            calls.append((by, value))
            return FakeElement()

    monkeypatch.setattr(message_detail, "_wait_until", lambda condition, timeout: True)

    assert message_detail._click_note_search_result_title(FakeDriver(), '骑行 "测试"') is True
    assert calls[0][0] == message_detail.AppiumBy.IOS_PREDICATE
    assert '骑行 \\"测试\\"' in calls[0][1]
    assert calls == [
        (message_detail.AppiumBy.IOS_PREDICATE, calls[0][1]),
        ("click",),
    ]


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


def test_android_detail_visible_while_real_content_is_loading():
    page_source = """
    <hierarchy>
      <android.widget.FrameLayout resource-id="post-detail-banner-pager" />
      <android.widget.TextView text="正在加载" />
      <android.widget.TextView text="正在加载真实详情内容。" />
    </hierarchy>
    """

    class FakeDriver:
        @property
        def page_source(self):
            return page_source

    assert message_detail.message_detail_is_visible(FakeDriver()) is True


def test_read_android_detail_accepts_image_note_without_body_when_shell_and_actions_are_visible(monkeypatch):
    page_source = """
    <hierarchy>
      <android.widget.FrameLayout resource-id="post-detail-banner-pager" />
      <android.widget.TextView text="耐热训练&#128545;" />
      <android.widget.TextView text="#骑行" />
      <android.widget.TextView text="1 天前" />
      <android.widget.TextView text="共 5 条评论" />
      <android.widget.TextView text="5" bounds="[751,2585][835,2657]" />
      <android.widget.TextView text="3" bounds="[953,2585][1037,2657]" />
      <android.widget.TextView text="5" bounds="[1154,2585][1238,2657]" />
    </hierarchy>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    snapshot = message_detail.read_message_detail_snapshot(FakeDriver(page_source), timeout=1)

    assert snapshot.title == "耐热训练😡"
    assert snapshot.body is None
    assert snapshot.comment_count == "5"
    assert snapshot.bottom_action_counts == ["5", "3", "5"]


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


def test_browse_android_detail_does_not_scroll_when_bottom_action_metadata_is_visible(monkeypatch):
    partial = message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"])
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(message_detail, "read_message_detail_snapshot", lambda driver, timeout: partial)
    monkeypatch.setattr(message_detail, "swipe_vertical", lambda driver, direction: events.append(direction))

    snapshot = message_detail.browse_note_detail(FakeDriver(), timeout=3)

    assert snapshot is partial
    assert events == []


def test_browse_android_detail_scrolls_when_interaction_metadata_is_missing(monkeypatch):
    partial = message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, [])
    complete = message_detail.MessageDetailSnapshot("标题", "正文", None, "0", [], "还没有评论", ["0", "0", "0"])
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(message_detail, "read_message_detail_snapshot", lambda driver, timeout: partial)
    monkeypatch.setattr(message_detail, "swipe_vertical", lambda driver, direction: events.append(direction))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "scrolled-detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: complete)

    snapshot = message_detail.browse_note_detail(FakeDriver(), timeout=3)

    assert snapshot.comment_count == "0"
    assert events == ["up"]


def test_parse_system_message_snapshot_detects_first_visible_message():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="系统消息" visible="true" />
      <XCUIElementTypeStaticText name="活动通知" visible="true" />
      <XCUIElementTypeStaticText name="07-31 17:45" visible="true" />
      <XCUIElementTypeStaticText name="有新的活动报名" visible="true" />
      <XCUIElementTypeStaticText name="有新的活动报名" visible="true" />
    </AppiumAUT>
    """

    snapshot = message_detail.parse_system_message_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.category == "活动通知"
    assert snapshot.timestamp == "07-31 17:45"
    assert snapshot.title == "有新的活动报名"
    assert snapshot.body == "有新的活动报名"
    assert snapshot.is_basic_system_message_visible()


def test_parse_system_message_snapshot_accepts_system_notification_category():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="系统消息" />
      <android.widget.TextView text="系统通知" />
      <android.widget.TextView text="08-04 15:15" />
      <android.widget.TextView text="订单退款成功" />
      <android.widget.TextView text="订单 RO17858276619742183FA 退款成功，退款金额：¥0.00，优惠券已退回账户" />
    </hierarchy>
    """

    snapshot = message_detail.parse_system_message_snapshot(page_source)

    assert snapshot.category == "系统通知"
    assert snapshot.timestamp == "08-04 15:15"
    assert snapshot.title == "订单退款成功"
    assert snapshot.is_basic_system_message_visible()


def test_open_system_message_page_taps_messages_tab_and_system_entry(monkeypatch):
    calls = []
    page = {"source": "首页 笔记 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        calls.append(("tap-tab", accessibility_id, text))
        page["source"] = "消息 系统通知 系统消息"
        return True

    def fake_tap_text(driver, text, timeout=1):
        calls.append(("tap-text", text))
        page["source"] = "系统消息 活动通知 07-31 17:45 有新的活动报名"
        return True

    monkeypatch.setattr(message_detail, "tap_accessibility_id_or_text_if_present", fake_tap_tab, raising=False)
    monkeypatch.setattr(message_detail, "tap_text_if_present", fake_tap_text)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    snapshot = message_detail.open_system_message_page(FakeDriver(), timeout=3)

    assert snapshot.is_basic_system_message_visible()
    assert calls == [
        ("tap-tab", "bottom-nav-messages", "消息"),
        ("tap-text", "系统消息"),
    ]


def test_open_system_message_page_reloads_message_network_error(monkeypatch):
    calls = []
    page = {"source": "首页 笔记 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        calls.append(("tap-tab", accessibility_id, text))
        page["source"] = "消息 通知加载失败 Network Error 重新加载 笔记 活动 消息 我的"
        return True

    def fake_tap_text(driver, text, timeout=1):
        calls.append(("tap-text", text))
        if text == "重新加载":
            page["source"] = "消息 系统通知 系统消息"
        elif text == "系统消息":
            page["source"] = "系统消息 活动通知 07-31 17:45 有新的活动报名"
        return True

    monkeypatch.setattr(message_detail, "tap_accessibility_id_or_text_if_present", fake_tap_tab, raising=False)
    monkeypatch.setattr(message_detail, "tap_text_if_present", fake_tap_text)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    snapshot = message_detail.open_system_message_page(FakeDriver(), timeout=3)

    assert snapshot.is_basic_system_message_visible()
    assert calls == [
        ("tap-tab", "bottom-nav-messages", "消息"),
        ("tap-text", "重新加载"),
        ("tap-text", "系统消息"),
    ]


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


def test_parse_detail_snapshot_extracts_android_comment_body():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="云南" bounds="[42,1331][220,1400]" />
      <android.widget.TextView text="共 1 条评论" bounds="[42,1841][1238,1910]" />
      <android.widget.TextView text="Nancy" bounds="[165,2121][292,2173]" />
      <android.widget.TextView text="云南" bounds="[165,2190][300,2250]" />
      <android.widget.TextView text="44 分钟前" bounds="[165,2280][320,2330]" />
      <android.widget.TextView text="回复" bounds="[920,2280][980,2330]" />
      <android.widget.TextView text="删除" bounds="[1020,2280][1080,2330]" />
      <android.widget.TextView text="0" bounds="[1180,2280][1220,2330]" />
      <android.widget.TextView text="Nancy" bounds="[150,2520][300,2600]" />
      <android.widget.TextView text="1" bounds="[750,2520][790,2600]" />
      <android.widget.TextView text="1" bounds="[930,2520][970,2600]" />
      <android.widget.TextView text="1" bounds="[1110,2520][1150,2600]" />
    </hierarchy>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.comment_count == "1"
    assert snapshot.comments == ["云南"]


def test_parse_detail_snapshot_extracts_bottom_action_counts():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="用户 abcdef 1 0 3" label="用户 abcdef 1 0 3" />
    </AppiumAUT>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.bottom_action_counts == ["1", "0", "3"]


def test_parse_detail_snapshot_uses_bottom_comment_action_count_when_comment_header_is_offscreen():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="Nancy" bounds="[164,560][308,617]" />
      <android.widget.TextView text="测试 - 这条笔记不错！！ 0804120304" bounds="[164,930][933,1000]" />
      <android.widget.TextView text="写留言" bounds="[173,260][330,330]" />
      <android.widget.TextView text="3" bounds="[730,2520][775,2600]" />
      <android.widget.TextView text="10" bounds="[930,2520][990,2600]" />
      <android.widget.TextView text="6" bounds="[1110,2520][1150,2600]" />
    </hierarchy>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.comment_count == "6"
    assert snapshot.bottom_action_counts == ["3", "10", "6"]


def test_parse_detail_snapshot_extracts_visible_android_comments_when_header_is_offscreen():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="Nancy" bounds="[165,544][292,596]" />
      <android.widget.TextView text="不错" bounds="[165,609][1208,674]" />
      <android.widget.TextView text="5 分钟前" bounds="[165,692][305,738]" />
      <android.widget.TextView text="回复" bounds="[916,690][994,739]" />
      <android.widget.TextView text="删除" bounds="[1023,690][1101,739]" />
      <android.widget.TextView text="0" bounds="[1183,690][1208,739]" />
      <android.widget.TextView text="Nancy" bounds="[165,860][292,912]" />
      <android.widget.TextView text="不错" bounds="[165,925][1208,990]" />
      <android.widget.TextView text="6 分钟前" bounds="[165,1008][305,1054]" />
      <android.widget.TextView text="回复" bounds="[916,1006][994,1055]" />
      <android.widget.TextView text="删除" bounds="[1023,1006][1101,1055]" />
      <android.widget.TextView text="0" bounds="[1183,1006][1208,1055]" />
      <android.widget.TextView text="2" bounds="[751,2585][835,2657]" />
      <android.widget.TextView text="8" bounds="[953,2585][1037,2657]" />
      <android.widget.TextView text="6" bounds="[1154,2585][1238,2657]" />
    </hierarchy>
    """

    snapshot = parse_detail_snapshot(page_source)

    assert snapshot.comment_count == "6"
    assert snapshot.comments == ["不错"]


def test_build_changbaishan_note_draft_uses_requested_content():
    draft = build_changbaishan_note_draft()

    assert draft.title == "测试 - 长白山真的有种让人瞬间安静下来的魔力"
    assert "第一次去长白山" in draft.body
    assert draft.topics == ["#长白山", "#旅行日记", "#治愈系风景", "#长白山天池", "#东北旅行"]
    assert draft.location == "长白山"
    assert draft.album == "图片"
    assert draft.allow_comments is True


def test_load_message_note_draft_reads_yaml_use_case():
    testdata_path = (
        Path(__file__).resolve().parent.parent / "message" / "testdata" / "publish_notes.yaml"
    )

    draft = load_message_note_draft("publish-note-changbaishan", testdata_path=testdata_path)

    assert draft.title == "测试 - 长白山真的有种让人瞬间安静下来的魔力"
    assert draft.album == "图片"
    assert draft.picture_index == 1
    assert draft.location == "长白山"


def test_load_message_note_draft_reads_no_location_variant(tmp_path):
    testdata_path = tmp_path / "publish_notes.yaml"
    testdata_path.write_text(
        """
use_cases:
  - id: publish-note-no-location
    note:
      title: 长白山真的有种让人瞬间安静下来的魔力
      body: 第一次去长白山，真的会被那种辽阔感击中。
      album: 长白山
      topics:
        - "#长白山"
      location:
      allow_comments: true
""",
        encoding="utf-8",
    )

    draft = load_message_note_draft("publish-note-no-location", testdata_path=testdata_path)

    assert draft.title == "长白山真的有种让人瞬间安静下来的魔力"
    assert draft.album == "长白山"
    assert draft.picture_index == 1
    assert draft.location == ""


def test_list_message_note_use_case_ids_reads_all_yaml_cases():
    testdata_path = (
        Path(__file__).resolve().parent.parent / "message" / "testdata" / "publish_notes.yaml"
    )

    use_case_ids = list_message_note_use_case_ids(testdata_path=testdata_path)

    assert "publish-note-changbaishan" in use_case_ids


def test_message_note_form_is_visible_from_publish_page_source():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="发布笔记" />
      <XCUIElementTypeTextField name="请输入标题" />
      <XCUIElementTypeTextView name="分享你的旅行故事" />
    </AppiumAUT>
    """

    assert message_note_form_is_visible(page_source) is True


def test_message_note_form_is_visible_from_android_publish_page_source():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="发布笔记" />
      <android.widget.TextView text="添加标题" />
      <android.widget.TextView text="输入正文" />
      <android.widget.TextView text="存草稿" />
      <android.widget.TextView text="提交审核" />
    </hierarchy>
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


def test_message_note_publish_success_signal_detects_video_upload_progress_on_my_notes():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="我的笔记" label="我的笔记" />
      <XCUIElementTypeOther name="进行中" label="进行中" />
    </AppiumAUT>
    """

    assert (
        message_note_publish_success_signal(page_source, allow_video_upload_progress=True)
        == "视频上传中"
    )


def test_message_note_publish_success_signal_detects_published_title_on_my_notes_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的笔记" />
      <XCUIElementTypeStaticText name="测试 - 长白山真的有种让人瞬间安静下来的魔力" />
      <XCUIElementTypeStaticText name="进行中" />
    </AppiumAUT>
    """

    assert (
        message_detail.message_note_publish_success_signal(
            page_source,
            published_title="测试 - 长白山真的有种让人瞬间安静下来的魔力",
        )
        == "我的笔记"
    )


def test_message_note_publish_success_signal_accepts_truncated_published_title_prefix_on_my_notes_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的笔记" />
      <XCUIElementTypeStaticText name="测试 - 长白山真的有种让人瞬间安静下来" />
      <XCUIElementTypeStaticText name="进行中" />
    </AppiumAUT>
    """

    assert (
        message_detail.message_note_publish_success_signal(
            page_source,
            published_title="测试 - 长白山真的有种让人瞬间安静下来的魔力",
        )
        == "我的笔记"
    )


def test_message_note_publish_success_signal_rejects_short_published_title_prefix_on_my_notes_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的笔记" />
      <XCUIElementTypeStaticText name="测试 - 长白山" />
      <XCUIElementTypeStaticText name="进行中" />
    </AppiumAUT>
    """

    assert (
        message_detail.message_note_publish_success_signal(
            page_source,
            published_title="测试 - 长白山真的有种让人瞬间安静下来的魔力",
        )
        is None
    )


def test_wait_for_video_upload_completion_returns_progress_signal_after_grace_period(monkeypatch):
    sources = iter(["我的笔记 进行中"])
    sleeps = []

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: next(sources, "我的笔记 进行中"))
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert message_detail.wait_for_video_upload_completion(object(), timeout=3, hold_seconds=2) == "视频上传中"
    assert sleeps == [2]


def test_wait_for_video_upload_completion_uses_observed_signal_without_repolling(monkeypatch):
    sleeps = []

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: pytest.fail("should not repoll page source"))
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: sleeps.append(seconds))

    assert (
        message_detail.wait_for_video_upload_completion(
            object(),
            timeout=3,
            hold_seconds=2,
            observed_signal="视频上传中",
        )
        == "视频上传中"
    )
    assert sleeps == [2]


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
    monkeypatch.setattr(message_detail, "_ensure_note_source_image_recorded", lambda driver: events.append("record-image"))
    monkeypatch.setattr(message_detail, "_fill_note_title", lambda driver, title: events.append(("title", title)) or True)
    monkeypatch.setattr(message_detail, "_fill_note_body", lambda driver, body: events.append(("body", body)) or True)
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
        "record-image",
        "wait-form",
        ("title", draft.title),
        ("body", draft.body),
        ("body-topics", draft.topics),
        ("location", draft.location),
        ("allow-comments", True),
    ]


def test_fill_message_note_form_skips_location_when_select_location_is_false(monkeypatch):
    events = []
    draft = MessageNoteDraft(
        title="长白山真的有种让人瞬间安静下来的魔力",
        body="第一次去长白山，真的会被那种辽阔感击中。",
        topics=["#长白山"],
        location="",
        album="长白山",
    )

    monkeypatch.setattr(message_detail, "wait_for_message_note_form", lambda driver, timeout: events.append("wait-form"))
    monkeypatch.setattr(message_detail, "_upload_note_image", lambda driver, draft: events.append(("upload-image", draft.album)))
    monkeypatch.setattr(message_detail, "_ensure_note_source_image_recorded", lambda driver: events.append("record-image"))
    monkeypatch.setattr(message_detail, "_fill_note_title", lambda driver, title: events.append(("title", title)) or True)
    monkeypatch.setattr(message_detail, "_fill_note_body", lambda driver, body: events.append(("body", body)) or True)
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
        "record-image",
        "wait-form",
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


def test_browse_note_detail_scrolls_android_when_comment_count_has_no_visible_comment(monkeypatch):
    first_snapshot = message_detail.MessageDetailSnapshot(
        title="出车出车",
        body="出去玩当然要方便，这个车车太能装啦#公路车#休闲骑#户外玩耍",
        view_count=None,
        comment_count="1",
        comments=[],
        empty_comment_hint=None,
        bottom_action_counts=["2", "1", "1"],
    )
    scrolled_source = """
    <hierarchy>
      <android.widget.TextView text="共 1 条评论" bounds="[42,320][1238,389]" />
      <android.widget.TextView text="爱骑车的菜腿丁教练" bounds="[149,430][632,489]" />
      <android.widget.TextView text="不错" bounds="[149,510][632,569]" />
      <android.widget.TextView text="5 分钟前" bounds="[149,590][330,639]" />
      <android.widget.TextView text="回复" bounds="[920,590][980,639]" />
      <android.widget.TextView text="0" bounds="[1180,590][1220,639]" />
      <android.widget.TextView text="2" bounds="[751,2585][835,2657]" />
      <android.widget.TextView text="1" bounds="[953,2585][1037,2657]" />
      <android.widget.TextView text="1" bounds="[1154,2585][1238,2657]" />
    </hierarchy>
    """
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(
        message_detail,
        "read_message_detail_snapshot",
        lambda driver, timeout=20: first_snapshot,
    )
    monkeypatch.setattr(
        message_detail,
        "swipe_vertical",
        lambda driver, direction="up": events.append(("swipe", direction)),
    )
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: scrolled_source)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    snapshot = message_detail.browse_note_detail(FakeDriver(), timeout=1)

    assert events == [("swipe", "up")]
    assert snapshot.comments == ["不错"]


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


def test_like_note_uses_element_center_fallback_when_first_tap_does_not_change_count(monkeypatch):
    events = []
    wait_results = iter([None, ["2", "0", "3"]])

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(
        message_detail,
        "parse_detail_snapshot",
        lambda source: message_detail.MessageDetailSnapshot(
            "标题",
            "正文",
            "4",
            "2",
            [],
            None,
            ["1", "0", "3"],
        ),
    )
    monkeypatch.setattr(
        message_detail,
        "_tap_bottom_action_at_index",
        lambda driver, action_index: events.append(("tap-bottom-action", action_index)) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_tap_bottom_action_element_center_at_index",
        lambda driver, action_index: events.append(("tap-bottom-action-center", action_index)) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_wait_for_bottom_action_count_change",
        lambda driver, action_index, before_counts, timeout: next(wait_results),
    )

    before, after = message_detail.like_note(driver=object(), timeout=3)

    assert before == ["1", "0", "3"]
    assert after == ["2", "0", "3"]
    assert events == [("tap-bottom-action", 0), ("tap-bottom-action-center", 0)]


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


def test_ios_bottom_action_taps_icon_center_by_index_from_source():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = """
        <AppiumAUT>
          <XCUIElementTypeOther name="不要再吃辣 1 1 1" visible="true" x="0" y="804" width="402" height="70">
            <XCUIElementTypeOther name="1 1 1" visible="true" x="204" y="813" width="185" height="26">
              <XCUIElementTypeOther name="1" visible="true" x="204" y="813" width="55" height="26">
                <XCUIElementTypeOther visible="true" x="204" y="813" width="26" height="26" />
                <XCUIElementTypeStaticText value="1" name="1" visible="true" x="232" y="814" width="27" height="24" />
              </XCUIElementTypeOther>
              <XCUIElementTypeOther name="1" visible="true" x="269" y="813" width="55" height="26">
                <XCUIElementTypeOther visible="true" x="269" y="813" width="26" height="26" />
                <XCUIElementTypeStaticText value="1" name="1" visible="true" x="297" y="814" width="27" height="24" />
              </XCUIElementTypeOther>
              <XCUIElementTypeOther name="1" visible="true" x="334" y="813" width="55" height="26">
                <XCUIElementTypeOther visible="true" x="334" y="813" width="26" height="26" />
                <XCUIElementTypeStaticText value="1" name="1" visible="true" x="362" y="814" width="27" height="24" />
              </XCUIElementTypeOther>
            </XCUIElementTypeOther>
          </XCUIElementTypeOther>
        </AppiumAUT>
        """

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_bottom_action_at_index(FakeDriver(), 0) is True
    assert taps == [("mobile: tap", {"x": 217, "y": 826})]


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


def test_submit_comment_uses_ios_set_value_and_verifies_full_text(monkeypatch):
    events = []
    entered = {"value": ""}

    class FakeInput:
        @staticmethod
        def click():
            events.append("click-input")

        @staticmethod
        def clear():
            events.append("clear")
            entered["value"] = ""

        @staticmethod
        def set_value(value):
            events.append(("set-value", value))
            entered["value"] = value

        @staticmethod
        def send_keys(value):
            events.append(("send-keys", value))

        @staticmethod
        def get_attribute(attribute):
            return entered["value"] if attribute == "value" else ""

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"]))
    monkeypatch.setattr(message_detail, "_tap_candidate", lambda driver, ids, texts: events.append(("tap-candidate", tuple(texts))) or True)
    monkeypatch.setattr(message_detail, "_find_comment_input", lambda driver, timeout: FakeInput())
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(message_detail, "_wait_for_comment_echo", lambda *args, **kwargs: events.append("wait-echo"))

    message_detail.submit_message_comment(FakeDriver(), "自动化测试留言", timeout=3)

    assert events == [
        ("tap-candidate", tuple(message_detail.COMMENT_ENTRY_TEXTS)),
        "click-input",
        "clear",
        ("set-value", "自动化测试留言"),
        ("tap-candidate", tuple(message_detail.COMMENT_SUBMIT_TEXTS)),
        "wait-echo",
    ]


def test_submit_comment_falls_back_to_ios_bottom_action_when_text_entry_does_not_open_input(monkeypatch):
    events = []
    input_attempts = iter([AssertionError("missing input"), object()])

    class FakeInput:
        @staticmethod
        def click():
            events.append("click-input")

        @staticmethod
        def clear():
            events.append("clear")

        @staticmethod
        def set_value(value):
            events.append(("set-value", value))

        @staticmethod
        def get_attribute(attribute):
            return "自动化测试留言" if attribute == "value" else ""

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    def fake_find_comment_input(driver, timeout):
        result = next(input_attempts)
        if isinstance(result, Exception):
            raise result
        return FakeInput()

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"]))
    monkeypatch.setattr(message_detail, "_tap_candidate", lambda driver, ids, texts: events.append(("tap-candidate", tuple(texts))) or True)
    monkeypatch.setattr(message_detail, "_tap_bottom_action_at_index", lambda driver, index: events.append(("tap-bottom-action", index)) or True)
    monkeypatch.setattr(message_detail, "_find_comment_input", fake_find_comment_input)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(message_detail, "_wait_for_comment_echo", lambda *args, **kwargs: events.append("wait-echo"))

    message_detail.submit_message_comment(FakeDriver(), "自动化测试留言", timeout=3)

    assert events == [
        ("tap-bottom-action", 2),
        ("tap-candidate", tuple(message_detail.COMMENT_ENTRY_TEXTS)),
        "click-input",
        "clear",
        ("set-value", "自动化测试留言"),
        ("tap-candidate", tuple(message_detail.COMMENT_SUBMIT_TEXTS)),
        "wait-echo",
    ]


def test_submit_comment_prefers_ios_bottom_action_before_candidate_scan(monkeypatch):
    events = []

    class FakeInput:
        @staticmethod
        def click():
            events.append("click-input")

        @staticmethod
        def clear():
            events.append("clear")

        @staticmethod
        def set_value(value):
            events.append(("set-value", value))

        @staticmethod
        def get_attribute(attribute):
            return "自动化测试留言" if attribute == "value" else ""

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "detail")
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"]))
    monkeypatch.setattr(message_detail, "_tap_bottom_action_at_index", lambda driver, index: events.append(("tap-bottom-action", index)) or True)
    monkeypatch.setattr(message_detail, "_find_comment_input", lambda driver, timeout: FakeInput())
    monkeypatch.setattr(message_detail, "_tap_candidate", lambda driver, ids, texts: events.append(("tap-candidate", tuple(texts))) or True)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(message_detail, "_wait_for_comment_echo", lambda *args, **kwargs: events.append("wait-echo"))

    message_detail.submit_message_comment(FakeDriver(), "自动化测试留言", timeout=3)

    assert events == [
        ("tap-bottom-action", 2),
        "click-input",
        "clear",
        ("set-value", "自动化测试留言"),
        ("tap-candidate", tuple(message_detail.COMMENT_SUBMIT_TEXTS)),
        "wait-echo",
    ]


def test_submit_comment_prefers_ios_visible_submit_text_from_source(monkeypatch):
    events = []

    class FakeInput:
        @staticmethod
        def click():
            events.append("click-input")

        @staticmethod
        def clear():
            events.append("clear")

        @staticmethod
        def set_value(value):
            events.append(("set-value", value))

        @staticmethod
        def get_attribute(attribute):
            return "自动化测试留言" if attribute == "value" else ""

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: """
        <AppiumAUT>
          <XCUIElementTypeStaticText name="发送" label="发送" visible="true" x="342" y="697" width="45" height="34" />
        </AppiumAUT>
        """,
    )
    monkeypatch.setattr(message_detail, "parse_detail_snapshot", lambda source: message_detail.MessageDetailSnapshot("标题", "正文", None, None, [], None, ["0", "0", "0"]))
    monkeypatch.setattr(message_detail, "_tap_bottom_action_at_index", lambda driver, index: events.append(("tap-bottom-action", index)) or True)
    monkeypatch.setattr(message_detail, "_find_comment_input", lambda driver, timeout: FakeInput())
    monkeypatch.setattr(message_detail, "_tap_candidate", lambda driver, ids, texts: events.append(("tap-candidate", tuple(texts))) or True)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())
    monkeypatch.setattr(message_detail, "_wait_for_comment_echo", lambda *args, **kwargs: events.append("wait-echo"))

    message_detail.submit_message_comment(FakeDriver(), "自动化测试留言", timeout=3)

    assert ("tap-candidate", tuple(message_detail.COMMENT_SUBMIT_TEXTS)) not in events
    assert ("mobile: tap", {"x": 364, "y": 714}) in events


def test_find_comment_input_supports_android_edit_text():
    expected = object()

    class FakeDriver:
        @staticmethod
        def find_element(by, value):
            if value == '//android.widget.EditText[@hint="写留言" or @text="写留言"]':
                return expected
            raise NoSuchElementException("no match")

    assert message_detail._find_comment_input(FakeDriver(), timeout=0.1) is expected


def test_close_ios_image_preview_taps_visible_top_right_close_button():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = """
        <AppiumAUT>
          <XCUIElementTypeApplication>
            <XCUIElementTypeWindow>
              <XCUIElementTypeOther visible="true" x="0" y="0" width="402" height="874">
                <XCUIElementTypeOther visible="true" x="0" y="0" width="402" height="104">
                  <XCUIElementTypeOther visible="true" x="13" y="70" width="376" height="34">
                    <XCUIElementTypeOther visible="true" x="355" y="70" width="34" height="34" />
                  </XCUIElementTypeOther>
                </XCUIElementTypeOther>
                <XCUIElementTypeOther name="post-detail-preview-pager" visible="true" x="0" y="0" width="402" height="874" />
                <XCUIElementTypeOther name="写留言" label="写留言" visible="false" x="13" y="715" width="376" height="39" />
              </XCUIElementTypeOther>
            </XCUIElementTypeWindow>
          </XCUIElementTypeApplication>
        </AppiumAUT>
        """

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._close_ios_image_preview_if_visible(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 372, "y": 87})]


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
    monkeypatch.setattr(
        message_detail,
        "_confirm_share_after_target",
        lambda driver, timeout: events.append(("confirm-share", timeout)) or True,
    )
    monkeypatch.setattr(
        message_detail,
        "_return_to_home_after_share",
        lambda driver, timeout: events.append(("return-home", timeout)) or True,
    )

    assert message_detail.share_note_to_moments(object(), timeout=6) == "朋友圈"
    assert events == [
        "tap-share",
        ("wait-until", 6),
        ("tap-share-target", "朋友圈"),
        ("confirm-share", 6),
        ("return-home", 6),
    ]


def test_tap_detail_share_button_uses_android_visible_header_icon_bounds(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_rect(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: """
        <hierarchy width="1280" height="2568">
          <android.view.ViewGroup bounds="[55,206][159,293]" />
          <android.view.ViewGroup bounds="[1115,202][1226,297]" />
        </hierarchy>
        """,
    )

    assert message_detail._tap_detail_share_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 1170, "y": 249})]


def test_tap_detail_share_button_uses_android_sticky_header_icon_near_status_bar(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_rect(self):
            return {"width": 1080, "height": 2400}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: """
        <hierarchy width="1080" height="2400">
          <android.view.ViewGroup bounds="[0,63][1080,223]" />
          <android.view.ViewGroup bounds="[45,112][129,182]" />
          <android.view.ViewGroup bounds="[944,107][1035,189]" />
        </hierarchy>
        """,
    )

    assert message_detail._tap_detail_share_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 989, "y": 148})]


def test_tap_detail_share_button_accepts_ios_detail_header_icon_below_status_bar():
    taps = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        @staticmethod
        def find_elements(by, value):
            return [
                FakeElement({"x": 39, "y": 182, "width": 42, "height": 42}),
                FakeElement({"x": 360, "y": 182, "width": 42, "height": 42}),
            ]

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    assert message_detail._tap_detail_share_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 381.0, "y": 203.0})]


def test_tap_detail_share_button_uses_ios_visible_header_icon_bounds_from_source(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            raise AssertionError("source fast path should run before element scan")

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: """
        <AppiumAUT>
          <XCUIElementTypeOther visible="true" x="39" y="182" width="42" height="42" />
          <XCUIElementTypeOther visible="true" x="360" y="182" width="42" height="42" />
        </AppiumAUT>
        """,
    )

    assert message_detail._tap_detail_share_button(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 381, "y": 203})]


def test_confirm_share_after_target_uses_android_top_right_coordinate_when_wechat_xml_is_empty(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_rect(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            events.append((script, payload))

    state = {"tapped": False}

    def fake_source(driver):
        if state["tapped"]:
            return "detail"
        return '<hierarchy><android.view.View package="com.tencent.mm" displayed="false" /></hierarchy>'

    monkeypatch.setattr(message_detail, "_safe_page_source", fake_source)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_share_returned_to_detail", lambda driver: message_detail._safe_page_source(driver) == "detail")
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    original_execute = FakeDriver.execute_script
    FakeDriver.execute_script = lambda self, script, payload: (original_execute(self, script, payload), state.update(tapped=True))

    assert message_detail._confirm_share_after_target(FakeDriver(), timeout=2) is True
    assert events == [("mobile: tap", {"x": 1126, "y": 221})]


def test_confirm_share_after_target_uses_ios_top_right_coordinate_when_wechat_xml_is_empty(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def get_window_rect(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            events.append((script, payload))
            state["tapped"] = True

    state = {"tapped": False}

    def fake_source(driver):
        if state["tapped"]:
            return "detail"
        return '<hierarchy><android.view.View package="com.tencent.mm" displayed="false" /></hierarchy>'

    monkeypatch.setattr(message_detail, "_safe_page_source", fake_source)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_share_returned_to_detail", lambda driver: message_detail._safe_page_source(driver) == "detail")
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._confirm_share_after_target(FakeDriver(), timeout=2) is True
    assert events == [("mobile: tap", {"x": 1126, "y": 221})]


def test_confirm_share_after_target_prefers_ios_top_right_coordinate_before_wait(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def get_window_rect(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "_share_returned_to_detail", lambda driver: False)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: events.append(("wait", timeout)) or True)

    assert message_detail._confirm_share_after_target(FakeDriver(), timeout=2) is True
    assert events[0] == ("mobile: tap", {"x": 1126, "y": 221})


def test_return_to_home_after_share_prefers_ios_header_back_from_source(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def back(self):
            raise AssertionError("iOS source back fast path should run before driver.back")

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(message_detail, "message_detail_is_visible", lambda driver: True)
    monkeypatch.setattr(
        message_detail,
        "_safe_page_source",
        lambda driver: """
        <AppiumAUT>
          <XCUIElementTypeOther visible="true" x="39" y="182" width="42" height="42" />
          <XCUIElementTypeOther visible="true" x="360" y="182" width="42" height="42" />
        </AppiumAUT>
        """,
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: events.append(("wait", timeout)) or True)

    assert message_detail._return_to_home_after_share(FakeDriver(), timeout=6) is True
    assert events == [
        ("mobile: tap", {"x": 60, "y": 203}),
        ("wait", 6),
    ]


def test_open_message_note_publisher_taps_publish_entry_before_note_type(monkeypatch):
    events = []
    page = {"source": ""}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: page["source"])
    monkeypatch.setattr(message_detail, "login_required_from_page_source", lambda source: False)
    monkeypatch.setattr(message_detail, "message_note_form_is_visible", lambda source: source == "message-note-form")
    monkeypatch.setattr(message_detail, "_tap_publish_entry_if_present", lambda driver: events.append("publish-entry") or True)
    monkeypatch.setattr(message_detail, "_tap_note_type_if_present", lambda driver: events.append("note-type") or True)
    monkeypatch.setattr(
        message_detail,
        "_wait_until",
        lambda predicate, timeout: page.update(source="message-note-form") or predicate(),
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    message_detail.open_message_note_publisher(object(), timeout=5)

    assert events[:2] == ["publish-entry", "note-type"]


def test_prepare_android_publish_entry_closes_search_page(monkeypatch):
    events = []
    page_sources = iter(['class="android.widget.EditText" text="搜索"', 'text="首页" text="活动" text="消息" text="我的"'])

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: next(page_sources))
    monkeypatch.setattr(message_detail, "_tap_android_header_close", lambda driver: events.append("header-close") or True)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    message_detail._prepare_android_publish_entry(FakeDriver())

    assert events == ["header-close"]


def test_android_search_page_visible_accepts_xiaomi_quicksearch_home():
    page_source = 'package="com.android.quicksearchbox" text="应用推荐" text="搜索"'

    assert message_detail._android_search_page_visible(page_source) is True


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
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, picture_index=1, select_all_from_album=True, retry_sheet_option=None, before_confirm_cropper=None: False,
    )

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
        message_detail,
        "_record_note_selected_album_image_source",
        lambda driver, draft: calls.append(("record-source", draft.album, draft.picture_index)),
    )
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_photo_from_library",
        lambda driver, album_name=None, picture_index=1, select_all_from_album=True, retry_sheet_option=None, before_confirm_cropper=None: calls.append(
            (
                "choose-photo",
                album_name,
                picture_index,
                select_all_from_album,
                retry_sheet_option is message_detail._tap_note_photo_library_sheet_option,
                before_confirm_cropper is None,
            )
        )
        or True,
    )

    message_detail._upload_note_image(object(), draft)

    assert calls == [
        "clear",
        "tap-plus",
        ("choose-photo", draft.album, draft.picture_index, False, True, True),
        ("record-source", draft.album, draft.picture_index),
    ]


def test_tap_note_photo_library_sheet_option_uses_row_center(monkeypatch):
    taps = []

    class FakeDriver:
        def get_window_size(self):
            return {"width": 440, "height": 956}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_photo_library_sheet_option(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 220.0, "y": 889.08})]


def test_load_message_note_draft_parses_video_media_type(tmp_path):
    testdata = tmp_path / "publish_notes.yaml"
    testdata.write_text(
        """use_cases:\n  - id: publish-note-video\n    note:\n      title: 视频标题\n      body: 视频正文\n      media_type: video\n      album: 视频\n      location: 长白山\n""",
        encoding="utf-8",
    )

    draft = load_message_note_draft("publish-note-video", testdata_path=testdata)

    assert draft.media_type == "video"
    assert draft.album == "视频"


def test_upload_note_media_uses_video_picker_without_image_validation(monkeypatch):
    calls = []
    draft = MessageNoteDraft(title="标题", body="正文", topics=[], location="", media_type="video", album="0424")

    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: calls.append("clear"))
    monkeypatch.setattr(message_detail, "_tap_note_video_entry", lambda driver: calls.append("tap-video") or True)
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_video_from_library",
        lambda driver, album_name=None, video_index=1: calls.append(("choose-video", album_name, video_index)) or True,
    )

    message_detail._upload_note_media(object(), draft)

    assert calls == ["clear", "tap-video", ("choose-video", "0424", 1)]


def test_upload_note_image_on_android_retries_remaining_picture_indexes(monkeypatch):
    calls = []
    state = {"count": 0}
    draft = MessageNoteDraft(
        title="title",
        body="body",
        topics=[],
        location="",
        album="云南洱海",
        picture_index=1,
        picture_indexes=(1, 2, 3),
    )

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    def choose_photo_from_library(
        driver,
        album_name=None,
        picture_index=1,
        picture_indexes=(),
        select_all_from_album=True,
        retry_sheet_option=None,
        before_confirm_cropper=None,
    ):
        calls.append(("choose-photo", album_name, picture_index, picture_indexes, select_all_from_album))
        if picture_indexes:
            state["count"] = 1
        else:
            state["count"] += 1
        return True

    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: calls.append("clear"))
    monkeypatch.setattr(message_detail, "_tap_note_image_plus", lambda driver: calls.append("tap-plus") or True)
    monkeypatch.setattr(message_detail.photo_picker, "choose_photo_from_library", choose_photo_from_library)
    monkeypatch.setattr(message_detail, "_note_selected_image_count", lambda driver: state["count"])
    monkeypatch.setattr(message_detail, "_wait_for_note_selected_image_count", lambda driver, expected_count: state["count"] >= expected_count)

    message_detail._upload_note_image(FakeDriver(), draft)

    assert calls == [
        "clear",
        "tap-plus",
        ("choose-photo", "云南洱海", 1, (1, 2, 3), True),
        "tap-plus",
        ("choose-photo", "云南洱海", 2, (), False),
        "tap-plus",
        ("choose-photo", "云南洱海", 3, (), False),
    ]


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


def test_android_note_image_plus_uses_updated_top_image_slot_from_source(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}
        page_source = """
        <hierarchy>
          <android.widget.FrameLayout resource-id="image" visible="true"
            x="14" y="132" width="96" height="96" />
        </hierarchy>
        """

        def execute_script(self, script, payload):
            taps.append((script, payload))

        def find_elements(self, by, value):
            raise AssertionError("coordinate fallback should not run when source hit is available")

    monkeypatch.setattr(message_detail, "_wait_for_note_photo_picker_opened", lambda driver, timeout=2: True)

    assert message_detail._tap_note_image_plus(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 62, "y": 156})]


def test_android_note_image_plus_uses_updated_vertical_media_card_from_source(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}
        page_source = """
        <hierarchy>
          <android.widget.ImageView resource-id="image" visible="true"
            x="0" y="354" width="250" height="827" />
        </hierarchy>
        """

        def execute_script(self, script, payload):
            taps.append((script, payload))

        def find_elements(self, by, value):
            raise AssertionError("coordinate fallback should not run when source hit is available")

    monkeypatch.setattr(message_detail, "_wait_for_note_photo_picker_opened", lambda driver, timeout=2: True)

    assert message_detail._tap_note_image_plus(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 125, "y": 436})]


def test_android_note_image_plus_uses_vertical_media_card_coordinate_fallback(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_elements(self, by, value):
            return []

        def get_window_size(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_for_note_photo_picker_opened", lambda driver, timeout=2: True)

    assert message_detail._tap_note_image_plus_by_coordinate(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 125.44, "y": 435.204})]


def test_android_note_video_entry_uses_vertical_media_card_lower_half():
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_size(self):
            return {"width": 1280, "height": 2772}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert message_detail._tap_note_video_entry(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 125.44, "y": 587.664})]


def test_ios_note_image_plus_uses_updated_top_image_slot_from_source(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = """
        <AppiumAUT>
          <XCUIElementTypeOther type="XCUIElementTypeOther" name="image" label="image"
            enabled="true" visible="true" accessible="false" x="14" y="132" width="96" height="96" />
        </AppiumAUT>
        """

        def execute_script(self, script, payload):
            taps.append((script, payload))

        def find_element(self, by, value):
            raise NoSuchElementException()

    monkeypatch.setattr(message_detail, "tap_if_present", lambda driver, value, timeout=1: False)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda driver, value, timeout=1: False)
    monkeypatch.setattr(message_detail, "_wait_for_note_photo_picker_opened", lambda driver, timeout=2: True)

    assert message_detail._tap_note_image_plus(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 62, "y": 156})]


def test_ios_note_image_plus_coordinate_fallback_requires_picker_transition(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_wait_for_note_photo_picker_opened", lambda driver, timeout=2: False)

    assert message_detail._tap_note_image_plus_by_coordinate(FakeDriver()) is False
    assert taps == [
        ("mobile: tap", {"x": 60, "y": 170}),
        ("mobile: tap", {"x": 66, "y": 190}),
        ("mobile: tap", {"x": 56, "y": 180}),
    ]


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


def test_fill_input_near_label_uses_ios_source_geometry(monkeypatch):
    events = []
    source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText visible="true" name="标题" x="13" y="280" width="60" height="24" />
      <XCUIElementTypeTextField visible="true" value="请输入标题" x="13" y="315" width="360" height="44" />
    </AppiumAUT>
    """

    class FakeElement:
        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_element(self, by, value):
            events.append(("find", by, value))
            if (
                by == message_detail.AppiumBy.XPATH
                and value == '//XCUIElementTypeTextField[@visible="true" and @x="13" and @y="315" and @width="360" and @height="44"]'
            ):
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: source)
    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    assert message_detail._fill_input_near_label(FakeDriver(), "标题", "长白山标题") is True
    assert events == [
        (
            "find",
            message_detail.AppiumBy.XPATH,
            '//XCUIElementTypeTextField[@visible="true" and @x="13" and @y="315" and @width="360" and @height="44"]',
        ),
        "click",
        "clear",
        ("send-keys", "长白山标题"),
        "hide-keyboard",
    ]


def test_replace_text_prefers_native_set_value_when_available():
    events = []

    class FakeElement:
        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def set_value(self, value):
            events.append(("set-value", value))

        def send_keys(self, value):
            events.append(("send-keys", value))

    message_detail._replace_text(FakeElement(), "长白山标题")

    assert events == ["click", "clear", ("set-value", "长白山标题")]


def test_fill_note_body_taps_android_emulator_text_placeholder(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {
            "platformName": "Android",
            "appium:udid": "emulator-5554",
            "appium:deviceName": "Android Emulator",
        }

        def find_element(self, by, value):
            if value == '//android.widget.EditText[@focused="true"]':
                return FakeElement()
            raise message_detail.NoSuchElementException()

    def tap_placeholder(driver, text, timeout=0):
        if text == "添加正文":
            events.append(("tap-text", text, timeout))
            return True
        return False

    monkeypatch.setattr(message_detail, "_fill_input_near_label", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "tap_text_if_present", tap_placeholder)
    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    message_detail._fill_note_body(FakeDriver(), "长白山正文")

    assert events == [
        ("tap-text", "添加正文", 1),
        "click-body",
        "clear-body",
        ("send-keys", "长白山正文"),
        "hide-keyboard",
    ]


def test_fill_note_body_does_not_use_emulator_placeholder_on_android_physical(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {
            "platformName": "Android",
            "appium:udid": "R5CN12345",
            "appium:deviceName": "Galaxy S24",
        }

        def find_element(self, by, value):
            events.append(("find", value))
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_fill_input_near_label", lambda *args, **kwargs: False)
    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda *args, **kwargs: events.append("tap") or True)

    with pytest.raises(AssertionError, match="Unable to locate the note body input"):
        message_detail._fill_note_body(FakeDriver(), "真机正文")

    assert "tap" not in events


def test_append_note_topics_uses_android_body_edit_text(monkeypatch):
    events = []

    class FakeElement:
        def get_attribute(self, name):
            if name == "text":
                return ""
            return None

        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

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
        "clear-body",
        ("send-keys", "#云南洱海 #大理旅行"),
        "hide-keyboard",
    ]


def test_append_note_topics_preserves_existing_android_body(monkeypatch):
    events = []

    class FakeElement:
        def get_attribute(self, name):
            if name == "text":
                return "今天骑行风很舒服"
            return None

        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

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

    message_detail._append_note_topics_to_body(FakeDriver(), ["#杭州徒步", "#西湖"])

    assert events == [
        "click-body",
        "clear-body",
        ("send-keys", "今天骑行风很舒服 #杭州徒步 #西湖"),
        "hide-keyboard",
    ]


def test_append_note_topics_falls_back_to_android_body_when_topic_action_missing(monkeypatch):
    events = []

    class FakeElement:
        def get_attribute(self, name):
            if name == "text":
                return "第一次去长白山"
            return None

        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//android.widget.EditText[contains(@hint, "正文")]':
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: False)
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: events.append("hide-keyboard"))

    message_detail._append_note_topics_to_body(FakeDriver(), ["#长白山", "#旅行日记"])

    assert events == [
        "click-body",
        "click-body",
        "clear-body",
        ("send-keys", "第一次去长白山 #长白山 #旅行日记"),
        "hide-keyboard",
    ]


def test_append_note_topics_refocuses_android_body_to_reveal_topic_action(monkeypatch):
    events = []

    class FakeElement:
        def get_attribute(self, name):
            if name == "text":
                return "第一次去长白山"
            return None

        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, value):
            if value == '//android.widget.EditText[contains(@hint, "正文")]':
                return FakeElement()
            raise message_detail.NoSuchElementException()

    def tap_topic_after_body_focus(driver, text):
        if text == "#话题" and events == ["click-body"]:
            events.append("tap-topic")
            return True
        return False

    monkeypatch.setattr(message_detail, "_tap_text_or_contains", tap_topic_after_body_focus)
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: events.append("hide-keyboard"))

    message_detail._append_note_topics_to_body(FakeDriver(), ["#长白山", "#旅行日记"])

    assert events == [
        "click-body",
        "tap-topic",
        "click-body",
        "clear-body",
        ("send-keys", "第一次去长白山 #长白山 #旅行日记"),
        "hide-keyboard",
    ]


def test_append_note_topics_uses_ios_body_geometry_without_topic_button(monkeypatch):
    events = []
    source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText visible="true" name="正文" x="13" y="390" width="60" height="24" />
      <XCUIElementTypeTextView visible="true" value="第一次去长白山" x="13" y="424" width="376" height="160" />
      <XCUIElementTypeStaticText visible="true" name="#话题" x="13" y="610" width="60" height="28" />
    </AppiumAUT>
    """

    class FakeElement:
        def get_attribute(self, attribute):
            if attribute == "value":
                return "第一次去长白山"
            return None

        def click(self):
            events.append("click-body")

        def clear(self):
            events.append("clear-body")

        def send_keys(self, value):
            events.append(("send-keys", value))

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_element(self, by, value):
            events.append(("find", by, value))
            if (
                by == message_detail.AppiumBy.XPATH
                and value == '//XCUIElementTypeTextView[@visible="true" and @x="13" and @y="424" and @width="376" and @height="160"]'
            ):
                return FakeElement()
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: source)
    monkeypatch.setattr(message_detail, "_tap_text_or_contains", lambda driver, text: events.append(("tap-topic", text)) or False)
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: events.append("hide-keyboard"))

    message_detail._append_note_topics_to_body(FakeDriver(), ["#长白山", "#旅行日记"])

    assert events == [
        (
            "find",
            message_detail.AppiumBy.XPATH,
            '//XCUIElementTypeTextView[@visible="true" and @x="13" and @y="424" and @width="376" and @height="160"]',
        ),
        "click-body",
        "clear-body",
        ("send-keys", "第一次去长白山 #长白山 #旅行日记"),
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


def test_android_detail_share_taps_sticky_header_action(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "")

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
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "发布笔记 标题 正文 已选择")
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


def test_find_android_note_image_remove_buttons_scopes_to_thumbnail_close_badges():
    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_elements(self, by, value):
            assert value == "//android.widget.HorizontalScrollView//android.view.ViewGroup"
            return [
                FakeElement({"x": 309, "y": 324, "width": 60, "height": 60}),
                FakeElement({"x": 663, "y": 324, "width": 60, "height": 60}),
                FakeElement({"x": 1017, "y": 324, "width": 60, "height": 60}),
                FakeElement({"x": 45, "y": 324, "width": 324, "height": 324}),
                FakeElement({"x": 753, "y": 588, "width": 66, "height": 60}),
            ]

    buttons = message_detail._find_note_image_remove_buttons(FakeDriver())

    assert [element.rect for element in buttons] == [
        {"x": 309, "y": 324, "width": 60, "height": 60},
        {"x": 663, "y": 324, "width": 60, "height": 60},
        {"x": 1017, "y": 324, "width": 60, "height": 60},
    ]


def test_note_selected_images_hint_accepts_android_thumbnail_strip():
    page_source = '发布笔记 <android.widget.ImageView resource-id="image" />'

    assert message_detail._note_selected_images_hint(page_source) is True


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


def test_tap_editor_done_targets_toolbar_control_center(monkeypatch):
    events = []

    class FakeElement:
        rect = {"x": 341, "y": 460, "width": 48, "height": 34}

    class FakeDriver:
        def find_element(self, by, value):
            events.append(("find-element", by, value))
            return FakeElement()

        def execute_script(self, script, payload):
            events.append(("execute", script, payload))

    monkeypatch.setattr(message_detail, "tap_text_if_present", lambda driver, text, timeout=2: False)
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
    monkeypatch.setattr(message_detail, "_dismiss_editor_keyboard", lambda driver: None)
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: True)
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


def test_choose_first_valid_location_from_picker_uses_ios_source_rect(monkeypatch):
    taps = []
    source = """
    <AppiumAUT>
      <XCUIElementTypeTextField visible="true" value="搜索地点" x="13" y="118" width="376" height="44" />
      <XCUIElementTypeOther visible="true" name="长白山国家级自然保护区 吉林省白山市" x="13" y="196" width="376" height="82" />
      <XCUIElementTypeOther visible="true" name="不标记地点" x="13" y="620" width="376" height="57" />
    </AppiumAUT>
    """

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            taps.append((script, payload))

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: source if not taps else "发布笔记 标记地点 长白山")
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: predicate())

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert taps == [("mobile: tap", {"x": 201, "y": 237})]


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
        "洱海公园 云南省大理白族自治州大理市滨海大道",
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
    assert taps == [("mobile: tap", {"x": 498.0, "y": 1542.8})]


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


def test_choose_android_location_falls_back_to_matching_result_row_when_text_taps_do_not_select(monkeypatch):
    waits = iter([False, False, True])
    visible_area_taps = []
    center_taps = []
    row_taps = []

    class FakeElement:
        def __init__(self, name, rect):
            self._name = name
            self.rect = rect

        def get_attribute(self, attribute):
            if attribute in {"text", "name", "label", "value"}:
                return self._name
            return None

    title = FakeElement(
        "长白山国家级自然保护区",
        {"x": 203, "y": 541, "width": 835, "height": 58},
    )
    row = FakeElement("", {"x": 161, "y": 509, "width": 919, "height": 185})

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def find_element(self, by, xpath):
            if (
                by == message_detail.AppiumBy.XPATH
                and 'contains(@text, "长白山国家级自然保护区")' in xpath
                and "ancestor::android.view.ViewGroup" in xpath
            ):
                return row
            raise message_detail.NoSuchElementException()

    monkeypatch.setattr(message_detail, "_find_location_result_elements", lambda driver: [title])
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
        "_tap_rect_center",
        lambda driver, rect: row_taps.append(rect) or True,
    )
    monkeypatch.setattr(message_detail, "_wait_until", lambda predicate, timeout: next(waits))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "标记地点 搜索地点 长白山")

    assert message_detail._choose_first_valid_location_from_picker(FakeDriver()) is True
    assert visible_area_taps == [title]
    assert center_taps == [title]
    assert row_taps == [{"x": 161.0, "y": 509.0, "width": 919.0, "height": 185.0}]


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


def test_ios_note_location_search_uses_visible_text_field(monkeypatch):
    events = []

    class FakeElement:
        def __init__(self, displayed, rect):
            self._displayed = displayed
            self.rect = rect

        def is_displayed(self):
            return self._displayed

        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def set_value(self, value):
            events.append(("set-value", value))

    hidden = FakeElement(False, {"x": 0, "y": 0, "width": 316, "height": 42})
    visible = FakeElement(True, {"x": 69, "y": 120, "width": 316, "height": 42})

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            events.append(("find-elements", value))
            return [hidden, visible]

    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "标记地点 长白山")
    monkeypatch.setattr(message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))
    monkeypatch.setattr(
        message_detail,
        "_tap_text_or_contains",
        lambda driver, text: events.append(("tap-text", text)) or True,
    )
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._search_note_location_from_picker(FakeDriver(), "长白山") is True
    assert events == [
        (
            "find-elements",
            '//XCUIElementTypeTextField[@value="搜索地点" or @name="搜索地点" or @label="搜索地点" or @placeholderValue="搜索地点"]',
        ),
        "click",
        "clear",
        ("set-value", "长白山"),
        "hide-keyboard",
        ("tap-text", "搜索"),
    ]


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


def test_search_note_location_waits_for_android_results_before_returning(monkeypatch):
    events = []
    result_batches = iter([[], [object()]])

    class FakeElement:
        def click(self):
            events.append("click")

        def clear(self):
            events.append("clear")

        def send_keys(self, value):
            events.append(("type", value))

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    def fake_wait_until(predicate, timeout):
        events.append(("wait-results", timeout))
        assert predicate() is False
        assert predicate() is True
        return True

    monkeypatch.setattr(message_detail, "_find_location_search_input", lambda driver: FakeElement())
    monkeypatch.setattr(message_detail, "_find_location_result_elements", lambda driver: next(result_batches))
    monkeypatch.setattr(message_detail, "_safe_page_source", lambda driver: "标记地点 搜索地点 长白山 搜索中...")
    monkeypatch.setattr(message_detail, "_wait_until", fake_wait_until)
    monkeypatch.setattr(message_detail.time, "sleep", lambda seconds: None)

    assert message_detail._search_note_location_from_picker(FakeDriver(), "长白山") is True
    assert events == [
        "click",
        "clear",
        ("type", "长白山"),
        ("wait-results", 10),
    ]


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
