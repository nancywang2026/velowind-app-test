import os
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException

from velowind_appium.config import (
    build_ios_capabilities,
    discover_first_online_ios_udid,
    load_ios_config,
)
from velowind_appium.actions import ACCESSIBILITY_ID_LOCATOR, _ios_predicate_string, find_visible_text_if_present, page_source_contains_any


def test_actions_use_appium_accessibility_id_locator():
    assert ACCESSIBILITY_ID_LOCATOR == "accessibility id"


def test_page_source_contains_any_matches_literal_text():
    assert page_source_contains_any("<App><Text>首页</Text></App>", ["首页", "消息"]) == "首页"
    assert page_source_contains_any("<App><Text>首页</Text></App>", ["活动"]) is None


def test_ios_predicate_string_escapes_quotes():
    assert _ios_predicate_string('说"好"') == '"说\\"好\\""'


def test_find_visible_text_if_present_returns_none_when_driver_never_matches():
    class StubDriver:
        def find_element(self, *_args, **_kwargs):
            raise NoSuchElementException("no match")

    assert find_visible_text_if_present(StubDriver(), ["首页", "消息"]) is None


def test_load_ios_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setattr("velowind_appium.config.auto_detect_online_ios_udid", lambda: None)
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-appium-config.yaml")
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
    assert config.target == "device"
    assert config.login_username is None
    assert config.login_password is None


def test_load_ios_config_reads_yaml_target_and_login(tmp_path, monkeypatch):
    config_file = tmp_path / "ios-appium.yaml"
    config_file.write_text(
        """
target: simulator
bundle_id: com.example.demo
no_reset: false
login:
  username: 13381509990
  password: 12345678
simulator:
  udid: SIM-001
  device_name: iPhone 17 Pro
  platform_version: "26.5"
  xcode_org_id: TEAM12345
  xcode_signing_id: Apple Development
  updated_wda_bundle_id: com.example.WebDriverAgentRunner
  web_driver_agent_url: http://127.0.0.1:8100
  allow_provisioning_device_registration: true
  show_xcode_log: true
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", str(config_file))
    monkeypatch.delenv("VW_IOS_UDID", raising=False)
    monkeypatch.setattr("velowind_appium.config.auto_detect_online_ios_udid", lambda: None)

    config = load_ios_config()

    assert config.target == "simulator"
    assert config.bundle_id == "com.example.demo"
    assert config.udid == "SIM-001"
    assert config.device_name == "iPhone 17 Pro"
    assert config.platform_version == "26.5"
    assert config.xcode_org_id == "TEAM12345"
    assert config.xcode_signing_id == "Apple Development"
    assert config.updated_wda_bundle_id == "com.example.WebDriverAgentRunner"
    assert config.web_driver_agent_url == "http://127.0.0.1:8100"
    assert config.allow_provisioning_device_registration is True
    assert config.show_xcode_log is True
    assert config.login_username == "13381509990"
    assert config.login_password == "12345678"
    assert config.no_reset is False


def test_env_overrides_yaml_target_specific_values(tmp_path, monkeypatch):
    config_file = tmp_path / "ios-appium.yaml"
    config_file.write_text(
        """
target: device
device:
  udid: DEVICE-001
login:
  username: 13381509990
  password: 12345678
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("VW_IOS_UDID", "DEVICE-OVERRIDE")
    monkeypatch.setenv("VW_IOS_TARGET", "simulator")
    monkeypatch.setenv("VW_IOS_DEVICE_NAME", "iPhone Override")
    monkeypatch.setenv("VW_IOS_PLATFORM_VERSION", "26.5")

    config = load_ios_config()

    assert config.target == "simulator"
    assert config.udid == "DEVICE-OVERRIDE"
    assert config.device_name == "iPhone Override"
    assert config.platform_version == "26.5"


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
    monkeypatch.setenv("VW_IOS_WDA_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("VW_IOS_SHOW_XCODE_LOG", "true")
    monkeypatch.setenv("VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION", "true")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:xcodeOrgId"] == "TEAM12345"
    assert capabilities["appium:xcodeSigningId"] == "Apple Development"
    assert capabilities["appium:updatedWDABundleId"] == "com.example.WebDriverAgentRunner"
    assert capabilities["appium:webDriverAgentUrl"] == "http://127.0.0.1:8100"
    assert capabilities["appium:showXcodeLog"] is True
    assert capabilities["appium:allowProvisioningDeviceRegistration"] is True


def test_build_ios_capabilities_includes_singleton_test_manager_override(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_SHOULD_USE_SINGLETON_TEST_MANAGER", "false")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:shouldUseSingletonTestManager"] is False


def test_build_ios_capabilities_includes_use_preinstalled_wda_override(monkeypatch):
    monkeypatch.setenv("VW_IOS_UDID", "device-001")
    monkeypatch.setenv("VW_IOS_USE_PREINSTALLED_WDA", "true")

    capabilities = build_ios_capabilities(load_ios_config())

    assert capabilities["appium:usePreinstalledWDA"] is True


def test_load_ios_config_auto_detects_online_device(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", "/tmp/non-existent-appium-config.yaml")
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
