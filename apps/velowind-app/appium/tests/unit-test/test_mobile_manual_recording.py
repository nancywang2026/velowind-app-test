import json
from pathlib import Path

import pytest

from velowind_appium.mobile_manual_recording import (
    capture_bug_snapshot,
    PlatformRuntime,
    build_environment_metadata,
    build_parser,
    default_recording_dir,
    main,
    resolve_platform_runtime,
    write_bug_recording_outputs,
)


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


def test_write_bug_recording_outputs_writes_json_report_and_taiga(tmp_path):
    from velowind_appium.bug_recording import BugCapture, BugRecording, SnapshotSummary

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
    assert paths["bug_report"].exists()
    assert paths["taiga_issue"].exists()
    assert "页面一直加载中" in paths["bug_report"].read_text(encoding="utf-8")
