from pathlib import Path

import pytest

from velowind_appium.bug_recording import BugCommand
from velowind_appium.mobile_manual_recording import (
    PlatformRuntime,
    build_environment_metadata,
    build_parser,
    default_recording_dir,
    main,
    resolve_platform_runtime,
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
    calls = {"parse_bug_command": [], "create_driver": 0}

    def fake_parse_bug_command(raw_command):
        calls["parse_bug_command"].append(raw_command)
        return BugCommand(kind="capture")

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
    monkeypatch.setattr("velowind_appium.bug_recording.parse_bug_command", fake_parse_bug_command)

    assert main(["--platform", "ios", "--mode", "bug"]) == 0
    assert calls["parse_bug_command"] == ["capture"]
    assert calls["create_driver"] == 0
