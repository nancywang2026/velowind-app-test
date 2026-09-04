from pathlib import Path
from types import SimpleNamespace

from velowind_appium.cleanup import CleanupReport
from velowind_appium import modules
from tests.message import xiaodai_video_upload
import velowind_appium.modules.message_detail as message_detail
import velowind_appium.modules.photo_picker as photo_picker


def _write_xiaodai_case(testdata: Path, source_video: str) -> None:
    testdata.write_text(
        f"""
use_cases:
  - id: xiaodai-0424
    note:
      source_video: {source_video}
""",
        encoding="utf-8",
    )


def test_xiaodai_source_video_path_uses_first_video_in_source_directory(tmp_path: Path, monkeypatch):
    data_root = tmp_path / "videos"
    source_dir = data_root / "小黛0424"
    source_dir.mkdir(parents=True)
    (source_dir / "02-second.mp4").write_bytes(b"second")
    (source_dir / "01-first.mov").write_bytes(b"first")
    (source_dir / "文案.png").write_bytes(b"image")
    testdata = tmp_path / "xiaodai.yaml"
    _write_xiaodai_case(testdata, "小黛0424")

    monkeypatch.setattr(xiaodai_video_upload, "TESTDATA_PATH", testdata)
    monkeypatch.setenv("VW_XIAODAI_DATA_ROOT", str(data_root))

    assert xiaodai_video_upload.xiaodai_source_video_path("xiaodai-0424") == source_dir / "01-first.mov"


def test_xiaodai_source_video_path_keeps_supporting_explicit_file_path(tmp_path: Path, monkeypatch):
    data_root = tmp_path / "videos"
    source_dir = data_root / "小黛0424"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "视频.mp4"
    source_file.write_bytes(b"video")
    testdata = tmp_path / "xiaodai.yaml"
    _write_xiaodai_case(testdata, "小黛0424/视频.mp4")

    monkeypatch.setattr(xiaodai_video_upload, "TESTDATA_PATH", testdata)
    monkeypatch.setenv("VW_XIAODAI_DATA_ROOT", str(data_root))

    assert xiaodai_video_upload.xiaodai_source_video_path("xiaodai-0424") == source_file


def test_xiaodai_source_video_path_accepts_album_prefixed_directory_name(tmp_path: Path, monkeypatch):
    data_root = tmp_path / "videos"
    source_dir = data_root / "0424"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "视频.mp4"
    source_file.write_bytes(b"video")
    testdata = tmp_path / "xiaodai.yaml"
    _write_xiaodai_case(testdata, "小黛0424")

    monkeypatch.setattr(xiaodai_video_upload, "TESTDATA_PATH", testdata)
    monkeypatch.setenv("VW_XIAODAI_DATA_ROOT", str(data_root))

    assert xiaodai_video_upload.xiaodai_source_video_path("xiaodai-0424") == source_file


def test_xiaodai_source_video_path_reports_missing_or_empty_source_directory(tmp_path: Path, monkeypatch):
    data_root = tmp_path / "videos"
    (data_root / "空目录").mkdir(parents=True)
    testdata = tmp_path / "xiaodai.yaml"
    monkeypatch.setattr(xiaodai_video_upload, "TESTDATA_PATH", testdata)
    monkeypatch.setenv("VW_XIAODAI_DATA_ROOT", str(data_root))

    _write_xiaodai_case(testdata, "不存在")
    try:
        xiaodai_video_upload.xiaodai_source_video_path("xiaodai-0424")
    except AssertionError as exc:
        assert "source video directory does not exist" in str(exc)
    else:
        raise AssertionError("missing source directory should fail")

    _write_xiaodai_case(testdata, "空目录")
    try:
        xiaodai_video_upload.xiaodai_source_video_path("xiaodai-0424")
    except AssertionError as exc:
        assert "contains no supported video files" in str(exc)
    else:
        raise AssertionError("empty source directory should fail")


def test_load_message_note_draft_reads_xiaodai_video_index(tmp_path: Path):
    testdata = tmp_path / "xiaodai.yaml"
    testdata.write_text(
        """
use_cases:
  - id: xiaodai-0424
    note:
      title: 标题
      body: 正文
      media_type: video
      video_index: 7
      topics:
        - "#话题"
""",
        encoding="utf-8",
    )

    draft = modules.load_message_note_draft("xiaodai-0424", testdata_path=testdata)

    assert draft.media_type == "video"
    assert draft.video_index == 7


def test_xiaodai_case_cleans_up_created_note_after_success(tmp_path: Path, monkeypatch):
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(b"video")
    draft = SimpleNamespace(
        title="Velowind｜解锁轻松骑行状态 🚲",
        caption_image="0424/文案.png",
        video_index=1,
    )
    events = []
    monkeypatch.setattr(xiaodai_video_upload, "load_message_note_draft", lambda *args, **kwargs: draft)
    monkeypatch.setattr(xiaodai_video_upload, "xiaodai_source_video_path", lambda *args: source_video)
    monkeypatch.setattr(xiaodai_video_upload, "ensure_logged_in_for_publish_entry", lambda *args: None)
    monkeypatch.setattr(xiaodai_video_upload, "publish_message_note", lambda *args, **kwargs: "已发布")
    monkeypatch.setattr(xiaodai_video_upload, "attach_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        xiaodai_video_upload,
        "load_cleanup_config",
        lambda: SimpleNamespace(delete_published_note_after_success=True),
    )
    monkeypatch.setattr(
        xiaodai_video_upload,
        "cleanup_published_note_after_success",
        lambda *args: events.append("delete") or CleanupReport("note", [draft.title], []),
    )

    def step(name, action):
        events.append(name)
        return action()

    xiaodai_video_upload.run_xiaodai_video_upload_case(object(), object(), step, "xiaodai-0424")

    assert events == [
        "prepare-home-session",
        "publish-xiaodai-video-xiaodai-0424",
        "cleanup-published-note-xiaodai-0424",
        "delete",
    ]


def test_upload_note_media_passes_draft_video_index_to_picker(monkeypatch):
    draft = modules.MessageNoteDraft(
        title="标题",
        body="正文",
        topics=[],
        location="",
        media_type="video",
        video_index=7,
    )
    calls = []

    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: calls.append("clear"))
    monkeypatch.setattr(message_detail, "_tap_note_video_entry", lambda driver: calls.append("tap-video") or True)
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_video_from_library",
        lambda driver, album_name=None, video_index=1: calls.append(("choose-video", album_name, video_index)) or True,
    )

    message_detail._upload_note_media(object(), draft)

    assert calls == ["clear", "tap-video", ("choose-video", None, 7)]


def test_upload_note_media_uses_camera_branch_for_recorded_video(monkeypatch):
    draft = modules.MessageNoteDraft(
        title="标题",
        body="正文",
        topics=[],
        location="",
        media_type="video",
        media_source="camera",
        video_index=7,
    )
    calls = []

    monkeypatch.setattr(message_detail, "_clear_existing_note_images", lambda driver: calls.append("clear"))
    monkeypatch.setattr(message_detail, "_tap_note_video_entry", lambda driver: calls.append("tap-video") or True)
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_video_from_camera",
        lambda driver, record_seconds=3: calls.append(("record-video", record_seconds)) or True,
    )
    monkeypatch.setattr(
        message_detail.photo_picker,
        "choose_video_from_library",
        lambda *args, **kwargs: calls.append("choose-library") or True,
    )

    message_detail._upload_note_media(object(), draft)

    assert calls == ["clear", "tap-video", ("record-video", 3)]


def test_ios_video_picker_uses_one_based_video_index(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, x):
            self.rect = {"x": x, "y": 160, "width": 100, "height": 100}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            return [FakeElement(10), FakeElement(130), FakeElement(250)]

        def execute_script(self, script, payload):
            taps.append(payload)

    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker._tap_first_ios_video_candidate(FakeDriver(), video_index=2) is True
    assert taps == [{"x": 180, "y": 210}]


def test_ios_album_video_picker_allows_large_video_preview_to_load(monkeypatch):
    waits = []

    class FakeElement:
        rect = {"x": 10, "y": 160, "width": 100, "height": 100}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            return [FakeElement()]

        def execute_script(self, script, payload):
            return None

    monkeypatch.setattr(
        photo_picker,
        "_wait_for_ios_video_preview",
        lambda driver, timeout: waits.append(timeout) or True,
    )

    assert photo_picker._tap_album_ios_video_candidate(FakeDriver()) is True
    assert waits == [30]


def test_ios_video_confirmation_waits_longer_for_large_video(monkeypatch):
    waits = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def execute_script(self, script, payload):
            return None

    monkeypatch.setattr(photo_picker, "_visible_text_present", lambda driver, text: False)
    monkeypatch.setattr(
        photo_picker,
        "_wait_for_ios_video_preview",
        lambda driver, timeout: waits.append(timeout) or False,
    )

    assert photo_picker._confirm_video_picker_selection(FakeDriver()) is False
    assert waits == [30]


def test_ios_video_picker_scrolls_when_index_is_beyond_first_page(monkeypatch):
    taps = []
    swipes = []

    class FakeElement:
        def __init__(self, x):
            self.rect = {"x": x, "y": 160, "width": 100, "height": 100}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def __init__(self):
            self.page = 0

        def find_elements(self, by, value):
            if self.page == 0:
                return [FakeElement(10), FakeElement(130)]
            return [FakeElement(250), FakeElement(370)]

        def execute_script(self, script, payload):
            if script == "mobile: swipe":
                swipes.append(payload)
                self.page = 1
            else:
                taps.append(payload)

    driver = FakeDriver()
    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker._tap_first_ios_video_candidate(driver, video_index=3) is True
    assert swipes == [{"direction": "up"}]
    assert taps == [{"x": 300, "y": 210}]


def test_ios_video_picker_counts_only_video_labeled_thumbnails():
    class FakeElement:
        def __init__(self, x, label):
            self.rect = {"x": x, "y": 160, "width": 100, "height": 100}
            self.label = label

        def get_attribute(self, name):
            return self.label if name in {"label", "name"} else None

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            return [
                FakeElement(10, "照片, 2026年8月24日, 10:00"),
                FakeElement(130, "视频, 六秒钟, 2026年8月24日, 09:59"),
            ]

    candidates = photo_picker._visible_ios_video_candidates(FakeDriver())

    assert len(candidates) == 1
    assert candidates[0][2]["x"] == 130


def test_ios_video_picker_reads_video_cells_when_images_are_not_exposed():
    class FakeElement:
        def __init__(self, x, label):
            self.rect = {"x": x, "y": 160, "width": 100, "height": 100}
            self.label = label

        def get_attribute(self, name):
            return self.label if name in {"label", "name"} else None

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def find_elements(self, by, value):
            if value == "//XCUIElementTypeImage":
                return []
            return [FakeElement(10, "视频, 六秒钟, 2026年8月24日, 10:00")]

    candidates = photo_picker._visible_ios_video_candidates(FakeDriver())

    assert len(candidates) == 1
    assert candidates[0][2]["x"] == 10


def test_ios_video_picker_reads_grid_thumbnails_from_page_source_when_wda_hides_images():
    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = '''
        <AppiumAUT>
          <XCUIElementTypeOther type="XCUIElementTypeOther" name="PXGGridLayout-Group" visible="true" x="0" y="0" width="402" height="874">
            <XCUIElementTypeImage type="XCUIElementTypeImage" name="PXGGridLayout-Info" label="照片, 2026年8月24日, 10:00" visible="true" x="0" y="160" width="134" height="134" />
            <XCUIElementTypeImage type="XCUIElementTypeImage" name="PXGGridLayout-Info" label="视频, 六秒钟, 2026年8月24日, 09:59" visible="true" x="134" y="160" width="134" height="134" />
          </XCUIElementTypeOther>
        </AppiumAUT>
        '''

        def find_elements(self, by, value):
            raise AssertionError("source parsing should handle this WDA response")

    candidates = photo_picker._visible_ios_video_candidates(FakeDriver())

    assert len(candidates) == 1
    assert candidates[0][2]["x"] == 134


def test_ios_video_picker_reads_button_thumbnails_from_page_source():
    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = '''
        <AppiumAUT>
          <XCUIElementTypeButton type="XCUIElementTypeButton" name="album-photo" label="照片, 六秒钟, 2026年8月24日, 10:00" visible="true" x="0" y="160" width="134" height="134" />
          <XCUIElementTypeButton type="XCUIElementTypeButton" name="album-video" label="视频, 六秒钟, 2026年8月24日, 09:59" visible="true" x="134" y="160" width="134" height="134" />
        </AppiumAUT>
        '''

        def find_elements(self, by, value):
            raise AssertionError("source parsing should handle button thumbnails")

    candidates = photo_picker._visible_ios_video_candidates(FakeDriver())

    assert len(candidates) == 1
    assert candidates[0][2]["x"] == 134


def test_ios_video_picker_reads_visible_false_accessible_true_video_cells_from_page_source():
    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = '''
        <AppiumAUT>
          <XCUIElementTypeOther type="XCUIElementTypeOther" name="PXGGridLayout-Group" visible="true" x="0" y="0" width="402" height="874">
            <XCUIElementTypeImage type="XCUIElementTypeImage" name="PXGGridLayout-Info" label="照片, 2026年8月24日, 10:00" visible="false" accessible="true" x="0" y="160" width="134" height="134" />
            <XCUIElementTypeImage type="XCUIElementTypeImage" name="PXGGridLayout-Info" label="视频, 十八秒钟, 2026年8月24日, 09:59" visible="false" accessible="true" x="134" y="160" width="134" height="134" />
          </XCUIElementTypeOther>
        </AppiumAUT>
        '''

        def find_elements(self, by, value):
            raise AssertionError("source parsing should handle visible=false accessible=true thumbnails")

    candidates = photo_picker._visible_ios_video_candidates(FakeDriver())

    assert len(candidates) == 1
    assert candidates[0][2]["x"] == 134


def test_ios_album_video_picker_clamps_to_visible_video_count(monkeypatch):
    taps = []

    class FakeElement:
        def __init__(self, x):
            self.rect = {"x": x, "y": 160, "width": 134, "height": 134}

    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = '''
        <AppiumAUT>
          <XCUIElementTypeImage type="XCUIElementTypeImage" name="PXGGridLayout-Info" label="视频, 十八秒钟, 4月24日, 14:28" visible="false" accessible="true" x="0" y="141" width="133" height="134" />
        </AppiumAUT>
        '''

        def find_elements(self, by, value):
            return [FakeElement(0)]

        def execute_script(self, script, payload):
            taps.append(payload)

    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker._tap_album_ios_video_candidate(FakeDriver(), video_index=10) is True
    assert taps == [{"x": 66.5, "y": 208.0}]


def test_ios_video_picker_does_not_count_unlabeled_other_containers_from_source():
    class FakeDriver:
        capabilities = {"platformName": "iOS"}
        page_source = '''
        <AppiumAUT>
          <XCUIElementTypeOther type="XCUIElementTypeOther" visible="true" x="0" y="160" width="134" height="134" />
          <XCUIElementTypeOther type="XCUIElementTypeOther" visible="true" x="134" y="160" width="134" height="134" />
        </AppiumAUT>
        '''

        def find_elements(self, by, value):
            return []

    assert photo_picker._visible_ios_video_candidates(FakeDriver()) == []


def test_ios_video_picker_coordinate_fallback_taps_bottom_left_for_video_ten(monkeypatch):
    taps = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def get_window_size(self):
            return {"width": 402, "height": 874}

        def execute_script(self, script, payload):
            taps.append(payload)

    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker._tap_ios_video_grid_coordinate_fallback(FakeDriver(), 10) is True
    assert taps == [{"x": 67.0, "y": 764.75}]


def test_choose_video_from_library_fails_when_no_video_candidate_was_tapped(monkeypatch):
    monkeypatch.setattr(photo_picker, "photo_library_visible", lambda driver, timeout=2: True)
    monkeypatch.setattr(photo_picker, "dismiss_photo_permission_alerts", lambda driver: None)
    monkeypatch.setattr(photo_picker, "_select_ios_video_filter", lambda driver: True)
    monkeypatch.setattr(photo_picker, "_tap_first_ios_video_candidate", lambda driver, video_index=1: False)
    monkeypatch.setattr(photo_picker, "_wait_for_ios_video_preview", lambda driver, timeout: True)

    assert photo_picker.choose_video_from_library(object(), video_index=10) is False
