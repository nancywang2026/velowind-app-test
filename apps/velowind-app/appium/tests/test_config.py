import os
from pathlib import Path

from velowind_appium.config import (
    build_ios_capabilities,
    discover_first_online_ios_udid,
    load_ios_config,
)
from velowind_appium.actions import ACCESSIBILITY_ID_LOCATOR, _ios_predicate_string, page_source_contains_any


def test_actions_use_appium_accessibility_id_locator():
    assert ACCESSIBILITY_ID_LOCATOR == "accessibility id"


def test_page_source_contains_any_matches_literal_text():
    assert page_source_contains_any("<App><Text>首页</Text></App>", ["首页", "消息"]) == "首页"
    assert page_source_contains_any("<App><Text>首页</Text></App>", ["活动"]) is None


def test_ios_predicate_string_escapes_quotes():
    assert _ios_predicate_string('说"好"') == '"说\\"好\\""'


def test_load_ios_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setattr("velowind_appium.config.auto_detect_online_ios_udid", lambda: None)
    for key in [
        "VW_APPIUM_SERVER_URL",
        "VW_IOS_UDID",
        "VW_IOS_BUNDLE_ID",
        "VW_IOS_APP",
        "VW_APPIUM_ARTIFACT_DIR",
        "VW_IOS_WAIT_FOR_IDLE_TIMEOUT",
        "VW_IOS_REDUCE_MOTION",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = load_ios_config()

    assert config.server_url == "http://127.0.0.1:4723"
    assert config.udid is None
    assert config.bundle_id == "com.velowind.rider"
    assert config.artifact_dir == Path(".tmp/appium-ios")
    assert config.wait_for_idle_timeout == 1.0
    assert config.reduce_motion is True


def test_build_ios_capabilities_prefers_installed_bundle(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_BUNDLE_ID", "com.example.demo")
    monkeypatch.delenv("VW_IOS_APP", raising=False)

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["platformName"] == "iOS"
    assert capabilities["appium:automationName"] == "XCUITest"
    assert capabilities["appium:udid"] == "device-001"
    assert capabilities["appium:bundleId"] == "com.example.demo"
    assert capabilities["appium:waitForIdleTimeout"] == 1.0
    assert capabilities["appium:reduceMotion"] is True
    assert "appium:app" not in capabilities


def test_build_ios_capabilities_allows_idle_wait_overrides(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_WAIT_FOR_IDLE_TIMEOUT", "0")
    monkeypatch.setenv("VW_IOS_REDUCE_MOTION", "false")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:waitForIdleTimeout"] == 0.0
    assert capabilities["appium:reduceMotion"] is False


def test_build_ios_capabilities_uses_app_path_when_provided(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_APP", "/tmp/VeloWind.app")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:app"] == "/tmp/VeloWind.app"
    assert "appium:bundleId" not in capabilities


def test_build_ios_capabilities_includes_optional_wda_signing(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_XCODE_ORG_ID", "TEAM12345")
    monkeypatch.setenv("VW_IOS_XCODE_SIGNING_ID", "Apple Development")
    monkeypatch.setenv("VW_IOS_UPDATED_WDA_BUNDLE_ID", "com.example.WebDriverAgentRunner")
    monkeypatch.setenv("VW_IOS_SHOW_XCODE_LOG", "true")
    monkeypatch.setenv("VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION", "true")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:xcodeOrgId"] == "TEAM12345"
    assert capabilities["appium:xcodeSigningId"] == "Apple Development"
    assert capabilities["appium:updatedWDABundleId"] == "com.example.WebDriverAgentRunner"
    assert capabilities["appium:showXcodeLog"] is True
    assert capabilities["appium:allowProvisioningDeviceRegistration"] is True


def test_load_ios_config_auto_detects_online_device(monkeypatch):
    monkeypatch.delenv("VW_IOS_UDID", raising=False)
    monkeypatch.setattr("velowind_appium.config.auto_detect_online_ios_udid", lambda: "device-auto")

    config = load_ios_config()

    assert config.udid == "device-auto"


def test_discover_first_online_ios_udid_ignores_offline_devices():
    output = """== Devices ==
Velowind's Mac (37BD1A53-5369-5383-9FFE-CCAE95F64E0C)
Zhigang的iPhone (26.2.1) (00008150-0006799C2693401C)

== Devices Offline ==
Test的iPhone (26.5.1) (00008150-001649663612401C)
"""

    assert discover_first_online_ios_udid(output) == "00008150-0006799C2693401C"


def test_discover_first_online_ios_udid_returns_none_when_only_offline():
    output = """== Devices ==
Velowind's Mac (37BD1A53-5369-5383-9FFE-CCAE95F64E0C)

== Devices Offline ==
Zhigang的iPhone (26.2.1) (00008150-0006799C2693401C)
"""

    assert discover_first_online_ios_udid(output) is None
