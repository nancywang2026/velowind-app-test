import json
from io import StringIO
from pathlib import Path

import pytest
from selenium.common.exceptions import WebDriverException

from velowind_appium.mobile_manual_recording import (
    _prompt,
    _review_recording,
    capture_bug_snapshot,
    PlatformRuntime,
    build_environment_metadata,
    build_parser,
    default_recording_dir,
    main,
    resolve_platform_runtime,
    record_bug_journey,
    write_bug_recording_outputs,
)
from velowind_appium.bug_recording import BugCapture, BugRecording, SnapshotSummary


def test_default_recording_dir_is_platform_specific():
    assert default_recording_dir("ios") == Path(".tmp/appium-ios/recordings")
    assert default_recording_dir("android") == Path(".tmp/appium-android/recordings")


def test_build_environment_metadata_for_ios_excludes_android_fields():
    config = type(
        "IosConfig",
        (),
        {
            "bundle_id": "com.velowind.rider",
            "server_url": "http://127.0.0.1:4723",
            "udid": "ios-device-001",
            "device_name": "Jiahao iPhone",
            "artifact_dir": Path(".tmp/appium-ios"),
            "platform_version": "18.5",
            "login_username": "tester@example.com",
        },
    )()

    metadata = build_environment_metadata("ios", config)

    assert metadata["platform"] == "ios"
    assert metadata["bundle_id"] == "com.velowind.rider"
    assert metadata["server_url"] == "http://127.0.0.1:4723"
    assert metadata["udid"] == "ios-device-001"
    assert metadata["device_name"] == "Jiahao iPhone"
    assert metadata["artifact_dir"] == ".tmp/appium-ios"
    assert metadata["platform_version"] == "18.5"
    assert metadata["login_username_present"] is True
    assert "app_package" not in metadata


def test_build_environment_metadata_for_android_excludes_ios_fields():
    config = type(
        "AndroidConfig",
        (),
        {
            "target": "android_studio",
            "server_url": "http://127.0.0.1:4724",
            "udid": "emulator-5554",
            "device_name": "Pixel 8",
            "app_package": "com.velowind.rider",
            "app_activity": ".MainActivity",
            "app_path": "/tmp/app.apk",
            "artifact_dir": Path(".tmp/appium-android"),
            "platform_version": "16",
            "login_username": None,
        },
    )()

    metadata = build_environment_metadata("android", config)

    assert metadata["platform"] == "android"
    assert metadata["target"] == "android_studio"
    assert metadata["app_package"] == "com.velowind.rider"
    assert metadata["app_activity"] == ".MainActivity"
    assert metadata["app_path"] == "/tmp/app.apk"
    assert metadata["platform_version"] == "16"
    assert metadata["login_username_present"] is False
    assert "bundle_id" not in metadata


def test_resolve_platform_runtime_rejects_unsupported_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        resolve_platform_runtime("web")


def test_resolve_platform_runtime_returns_supported_runtime_names():
    assert resolve_platform_runtime("ios").platform == "ios"
    assert resolve_platform_runtime("android").platform == "android"


def test_build_parser_accepts_taiga_project():
    parser = build_parser()

    args = parser.parse_args(["--platform", "ios", "--taiga-project", "velowind"])

    assert args.taiga_project == "velowind"


def test_main_accepts_package_manager_help_separator(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--platform", "android", "--", "--help"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Record manual mobile app interactions and bug evidence." in captured.out


def test_main_accepts_package_manager_help_separator_from_sys_argv(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "mobile_manual_recording.py",
            "--platform",
            "android",
            "--",
            "--help",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Record manual mobile app interactions and bug evidence." in captured.out


def test_bug_mode_returns_without_starting_driver(monkeypatch):
    calls = {"record_bug_journey": 0, "create_driver": 0}

    def fake_record_bug_journey(args, runtime):
        calls["record_bug_journey"] += 1
        return 0

    def fail_create_driver(config):
        calls["create_driver"] += 1
        raise AssertionError("bug mode must not create an Appium driver")

    fake_runtime = PlatformRuntime(
        platform="ios",
        load_config=lambda: object(),
        create_driver=fail_create_driver,
    )

    monkeypatch.setattr(
        "velowind_appium.mobile_manual_recording.resolve_platform_runtime",
        lambda platform: fake_runtime,
    )
    monkeypatch.setattr("velowind_appium.mobile_manual_recording.record_bug_journey", fake_record_bug_journey)

    assert main(["--platform", "ios", "--mode", "bug"]) == 0
    assert calls["record_bug_journey"] == 1
    assert calls["create_driver"] == 0


class FakeDriver:
    page_source = """
    <AppiumAUT>
      <node visible="true" content-desc="search-input" text="搜索" />
      <node visible="true" content-desc="loading-title" text="正在加载真实搜索结果" />
    </AppiumAUT>
    """

    def save_screenshot(self, path):
        Path(path).write_bytes(b"fake-png")


def test_capture_bug_snapshot_writes_screenshot_and_xml(tmp_path):
    snapshot = capture_bug_snapshot(FakeDriver(), tmp_path, "01-loading")

    assert snapshot.screenshot_path is not None
    assert snapshot.xml_path is not None
    assert "search-input" in snapshot.visible_ids
    assert "搜索" in snapshot.visible_texts
    assert snapshot.capture_error is None


class ScreenshotFailureDriver(FakeDriver):
    def save_screenshot(self, path):
        raise WebDriverException("screenshot failed")


def test_capture_bug_snapshot_reports_missing_artifacts_when_capture_helper_swallows_failure(tmp_path):
    snapshot = capture_bug_snapshot(ScreenshotFailureDriver(), tmp_path, "01-loading")

    assert snapshot.screenshot_path is None
    assert snapshot.xml_path is not None
    assert snapshot.capture_error == "Missing capture artifacts: PNG"


class PageSourceFailureDriver(FakeDriver):
    @property
    def page_source(self):
        raise WebDriverException("page source failed")


def test_capture_bug_snapshot_preserves_page_source_webdriver_error(tmp_path):
    snapshot = capture_bug_snapshot(PageSourceFailureDriver(), tmp_path, "01-loading")

    assert snapshot.screenshot_path is not None
    assert snapshot.xml_path is None
    assert snapshot.capture_error is not None
    assert "WebDriverException" in snapshot.capture_error
    assert "page source failed" in snapshot.capture_error


def test_write_bug_recording_outputs_writes_json_report_and_taiga(tmp_path):
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="搜索结果持续加载",
        environment={"platform": "ios", "bundle_id": "com.velowind.rider"},
        expected_result="应展示搜索结果",
        actual_result="页面一直加载中",
        notes=[],
        captures=[
            BugCapture(
                1,
                "loading",
                "页面持续加载",
                None,
                "2026-07-24T10:00:00",
                SnapshotSummary("/tmp/1.png", "/tmp/1.xml", "a", [], [], None),
            ),
        ],
    )

    paths = write_bug_recording_outputs(recording, tmp_path)

    payload = json.loads(paths["recording"].read_text(encoding="utf-8"))
    assert payload["mode"] == "bug"
    assert payload["actual_result"] == "页面一直加载中"
    assert payload["steps"][0]["description"] == "页面持续加载"
    assert paths["bug_report"].exists()
    assert paths["taiga_issue"].exists()
    assert "页面一直加载中" in paths["bug_report"].read_text(encoding="utf-8")
    assert "页面一直加载中" in paths["taiga_issue"].read_text(encoding="utf-8")


def test_prompt_returns_none_on_eof_but_blank_line_remains_blank(monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO(""))
    monkeypatch.setattr("sys.stdout", StringIO())

    assert _prompt("bug> ") is None

    monkeypatch.setattr("sys.stdin", StringIO("\n"))

    assert _prompt("bug> ") == ""


def test_review_recording_keeps_current_recording_on_eof(monkeypatch):
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="search-loading",
        environment={"platform": "ios"},
        expected_result="",
        actual_result="",
        notes=[],
        captures=[
            BugCapture(0, "initial", "初始页面", None, "2026-07-24T10:00:00", SnapshotSummary(None, None, "a", [], [], None)),
            BugCapture(1, "loading", "页面加载", None, "2026-07-24T10:01:00", SnapshotSummary(None, None, "b", [], [], None)),
        ],
    )

    monkeypatch.setattr("velowind_appium.mobile_manual_recording._prompt", lambda _message: None)

    assert _review_recording(recording) == recording


def test_record_bug_journey_keeps_initial_capture_in_final_recording(tmp_path, monkeypatch):
    class FakeDriver:
        page_source = "<AppiumAUT><node visible='true' text='初始页面' /></AppiumAUT>"

        def save_screenshot(self, path):
            Path(path).write_bytes(b"fake-png")

        def quit(self):
            pass

    recorded = {}

    def fake_create_driver(config):
        return FakeDriver()

    def fake_load_config():
        return object()

    def fake_prompt(_message):
        return next(prompts)

    def fake_write_bug_recording_outputs(recording, artifact_dir):
        recorded["recording"] = recording
        return {"bug_report": artifact_dir / "bug-report.md", "taiga_issue": artifact_dir / "taiga-issue.md", "recording": artifact_dir / "recording.json"}

    prompts = iter(["actual 页面一直加载中", "done", "keep", "n"])
    runtime = PlatformRuntime(platform="ios", load_config=fake_load_config, create_driver=fake_create_driver)
    args = type("Args", (), {"output_dir": str(tmp_path), "session_name": "search-loading"})()

    monkeypatch.setattr("velowind_appium.mobile_manual_recording._prompt", fake_prompt)
    monkeypatch.setattr("velowind_appium.mobile_manual_recording.write_bug_recording_outputs", fake_write_bug_recording_outputs)

    assert record_bug_journey(args, runtime) == 0
    assert [capture.index for capture in recorded["recording"].captures] == [0]
    assert recorded["recording"].captures[0].description == "初始页面"


def test_record_bug_journey_finishes_gracefully_when_bug_prompt_reaches_eof(tmp_path, monkeypatch):
    class FakeDriver:
        page_source = "<AppiumAUT><node visible='true' text='初始页面' /></AppiumAUT>"

        def save_screenshot(self, path):
            Path(path).write_bytes(b"fake-png")

        def quit(self):
            pass

    recorded = {}

    def fake_create_driver(config):
        return FakeDriver()

    def fake_load_config():
        return object()

    def fake_write_bug_recording_outputs(recording, artifact_dir):
        recorded["recording"] = recording
        return {"bug_report": artifact_dir / "bug-report.md", "taiga_issue": artifact_dir / "taiga-issue.md", "recording": artifact_dir / "recording.json"}

    runtime = PlatformRuntime(platform="ios", load_config=fake_load_config, create_driver=fake_create_driver)
    args = type("Args", (), {"output_dir": str(tmp_path), "session_name": "search-loading"})()

    monkeypatch.setattr("velowind_appium.mobile_manual_recording._prompt", lambda _message: None)
    monkeypatch.setattr("velowind_appium.mobile_manual_recording.write_bug_recording_outputs", fake_write_bug_recording_outputs)

    assert record_bug_journey(args, runtime) == 0
    assert [capture.index for capture in recorded["recording"].captures] == [0]


def test_record_bug_journey_generates_ios_test_when_confirmed(tmp_path, monkeypatch):
    class FakeDriver:
        page_source = "<AppiumAUT><node visible='true' text='初始页面' /></AppiumAUT>"

        def save_screenshot(self, path):
            Path(path).write_bytes(b"fake-png")

        def quit(self):
            pass

    recorded = {}
    generated_paths = []

    def fake_create_driver(config):
        return FakeDriver()

    def fake_load_config():
        return object()

    def fake_prompt(_message):
        return next(prompts)

    def fake_write_bug_recording_outputs(recording, artifact_dir):
        recorded["recording"] = recording
        recording_path = artifact_dir / "recording.json"
        return {
            "bug_report": artifact_dir / "bug-report.md",
            "taiga_issue": artifact_dir / "taiga-issue.md",
            "recording": recording_path,
        }

    def fake_generate_test_module(recording_path):
        generated_paths.append(recording_path)
        return recording_path.with_name("test_search_loading.py")

    prompts = iter(["actual 页面一直加载中", "done", "keep", "y"])
    runtime = PlatformRuntime(platform="ios", load_config=fake_load_config, create_driver=fake_create_driver)
    args = type("Args", (), {"output_dir": str(tmp_path), "session_name": "search-loading"})()

    monkeypatch.setattr("velowind_appium.mobile_manual_recording._prompt", fake_prompt)
    monkeypatch.setattr("velowind_appium.mobile_manual_recording.write_bug_recording_outputs", fake_write_bug_recording_outputs)
    monkeypatch.setattr(
        "velowind_appium.generate_ios_test_from_recording.generate_test_module",
        fake_generate_test_module,
    )

    assert record_bug_journey(args, runtime) == 0
    assert recorded["recording"].actual_result == "页面一直加载中"
    assert generated_paths == [tmp_path / "search-loading" / "recording.json"]


def test_record_bug_journey_prints_android_generation_message(tmp_path, monkeypatch, capsys):
    class FakeDriver:
        page_source = "<AppiumAUT><node visible='true' text='初始页面' /></AppiumAUT>"

        def save_screenshot(self, path):
            Path(path).write_bytes(b"fake-png")

        def quit(self):
            pass

    def fake_create_driver(config):
        return FakeDriver()

    def fake_load_config():
        return object()

    def fake_prompt(_message):
        return next(prompts)

    def fake_write_bug_recording_outputs(recording, artifact_dir):
        return {
            "bug_report": artifact_dir / "bug-report.md",
            "taiga_issue": artifact_dir / "taiga-issue.md",
            "recording": artifact_dir / "recording.json",
        }

    prompts = iter(["actual 页面一直加载中", "done", "keep"])
    runtime = PlatformRuntime(platform="android", load_config=fake_load_config, create_driver=fake_create_driver)
    args = type("Args", (), {"output_dir": str(tmp_path), "session_name": "search-loading"})()

    monkeypatch.setattr("velowind_appium.mobile_manual_recording._prompt", fake_prompt)
    monkeypatch.setattr("velowind_appium.mobile_manual_recording.write_bug_recording_outputs", fake_write_bug_recording_outputs)

    assert record_bug_journey(args, runtime) == 0
    output = capsys.readouterr().out
    assert "Android script generation will be added separately." in output
