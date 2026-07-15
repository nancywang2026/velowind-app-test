from pathlib import Path

import pytest

from velowind_appium.android_config import (
    build_android_capabilities,
    discover_first_online_android_udid,
    load_android_config,
)


def test_discover_first_online_android_udid_skips_offline_and_non_emulator():
    adb_output = """
List of devices attached
R5CN12345	device
emulator-5554	offline
emulator-5556	device
"""

    assert discover_first_online_android_udid(adb_output) == "emulator-5556"


def test_load_android_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setattr("velowind_appium.android_config.auto_detect_online_android_udid", lambda: None)
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-android-appium.yaml")
    for key in [
        "VW_APPIUM_SERVER_URL",
        "VW_ANDROID_TARGET",
        "VW_ANDROID_UDID",
        "VW_ANDROID_DEVICE_NAME",
        "VW_ANDROID_APP",
        "VW_ANDROID_APP_PACKAGE",
        "VW_ANDROID_APP_ACTIVITY",
        "VW_ANDROID_PLATFORM_VERSION",
        "VW_ANDROID_NO_RESET",
        "VW_ANDROID_AUTO_GRANT_PERMISSIONS",
        "VW_APPIUM_ARTIFACT_DIR",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_android_config()

    assert config.target == "emulator"
    assert config.server_url == "http://127.0.0.1:4723"
    assert config.udid is None
    assert config.device_name == "Android Emulator"
    assert config.app_path is None
    assert config.app_package == "com.velowind.rider"
    assert config.app_activity is None
    assert config.artifact_dir == Path(".tmp/appium-android")
    assert config.no_reset is True
    assert config.auto_grant_permissions is True


def test_load_android_config_reads_yaml_and_login(tmp_path, monkeypatch):
    config_file = tmp_path / "android-appium.yaml"
    config_file.write_text(
        """
target: emulator
app_package: com.example.demo
app_activity: .MainActivity
no_reset: false
auto_grant_permissions: false
login:
  username: 13381509990
  password: 12345678
emulator:
  udid: emulator-5556
  device_name: Pixel 8
  platform_version: "15"
  app_path: /tmp/demo.apk
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("VW_ANDROID_UDID", raising=False)
    monkeypatch.setattr("velowind_appium.android_config.auto_detect_online_android_udid", lambda: None)

    config = load_android_config()

    assert config.target == "emulator"
    assert config.udid == "emulator-5556"
    assert config.device_name == "Pixel 8"
    assert config.platform_version == "15"
    assert config.app_path == "/tmp/demo.apk"
    assert config.app_package == "com.example.demo"
    assert config.app_activity == ".MainActivity"
    assert config.no_reset is False
    assert config.auto_grant_permissions is False
    assert config.login_username == "13381509990"
    assert config.login_password == "12345678"


def test_env_overrides_android_yaml(tmp_path, monkeypatch):
    config_file = tmp_path / "android-appium.yaml"
    config_file.write_text(
        """
target: emulator
app_package: com.example.demo
app_activity: .MainActivity
emulator:
  udid: emulator-5556
  device_name: Pixel 8
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("VW_ANDROID_UDID", "emulator-5560")
    monkeypatch.setenv("VW_ANDROID_DEVICE_NAME", "Pixel Override")
    monkeypatch.setenv("VW_ANDROID_PLATFORM_VERSION", "16")
    monkeypatch.setenv("VW_ANDROID_APP_PACKAGE", "com.override.demo")
    monkeypatch.setenv("VW_ANDROID_APP_ACTIVITY", ".OverrideActivity")

    config = load_android_config()

    assert config.udid == "emulator-5560"
    assert config.device_name == "Pixel Override"
    assert config.platform_version == "16"
    assert config.app_package == "com.override.demo"
    assert config.app_activity == ".OverrideActivity"


def test_build_android_capabilities_uses_apk_when_provided(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-android-appium.yaml")
    monkeypatch.setenv("VW_ANDROID_UDID", "emulator-5554")
    monkeypatch.setenv("VW_ANDROID_APP", "/tmp/velowind.apk")
    monkeypatch.delenv("VW_ANDROID_APP_ACTIVITY", raising=False)

    capabilities = build_android_capabilities(load_android_config())

    assert capabilities["platformName"] == "Android"
    assert capabilities["appium:automationName"] == "UiAutomator2"
    assert capabilities["appium:udid"] == "emulator-5554"
    assert capabilities["appium:app"] == "/tmp/velowind.apk"
    assert capabilities["appium:appPackage"] == "com.velowind.rider"
    assert "appium:appActivity" not in capabilities


def test_build_android_capabilities_uses_installed_app_when_no_apk(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-android-appium.yaml")
    monkeypatch.setenv("VW_ANDROID_UDID", "emulator-5554")
    monkeypatch.delenv("VW_ANDROID_APP", raising=False)
    monkeypatch.setenv("VW_ANDROID_APP_PACKAGE", "com.example.demo")
    monkeypatch.setenv("VW_ANDROID_APP_ACTIVITY", ".MainActivity")

    capabilities = build_android_capabilities(load_android_config())

    assert "appium:app" not in capabilities
    assert capabilities["appium:appPackage"] == "com.example.demo"
    assert capabilities["appium:appActivity"] == ".MainActivity"
    assert capabilities["appium:autoGrantPermissions"] is True


def test_build_android_capabilities_requires_udid(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-android-appium.yaml")
    monkeypatch.delenv("VW_ANDROID_UDID", raising=False)
    monkeypatch.setattr("velowind_appium.android_config.auto_detect_online_android_udid", lambda: None)

    with pytest.raises(RuntimeError, match="No online Android emulator"):
        build_android_capabilities(load_android_config())


def test_build_android_capabilities_requires_activity_without_apk(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-android-appium.yaml")
    monkeypatch.setenv("VW_ANDROID_UDID", "emulator-5554")
    monkeypatch.delenv("VW_ANDROID_APP", raising=False)
    monkeypatch.delenv("VW_ANDROID_APP_ACTIVITY", raising=False)

    with pytest.raises(RuntimeError, match="VW_ANDROID_APP_ACTIVITY"):
        build_android_capabilities(load_android_config())
