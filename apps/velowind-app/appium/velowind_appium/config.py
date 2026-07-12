from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Dict, Optional
import yaml


DEFAULT_SERVER_URL = "http://127.0.0.1:4723"
DEFAULT_BUNDLE_ID = "com.velowind.rider"
DEFAULT_ARTIFACT_DIR = Path(".tmp/appium-ios")
DEFAULT_CONFIG_FILE = Path(__file__).resolve().parents[1] / "ios-appium.yaml"


@dataclass(frozen=True)
class IosAppiumConfig:
    target: str
    server_url: str
    udid: Optional[str]
    bundle_id: str
    app_path: Optional[str]
    artifact_dir: Path
    platform_version: Optional[str]
    device_name: Optional[str]
    xcode_org_id: Optional[str]
    xcode_signing_id: Optional[str]
    updated_wda_bundle_id: Optional[str]
    show_xcode_log: bool
    allow_provisioning_device_registration: bool
    use_new_wda: bool
    use_preinstalled_wda: Optional[bool]
    no_reset: bool
    wait_for_idle_timeout: float
    reduce_motion: bool
    should_use_singleton_test_manager: Optional[bool]
    login_username: Optional[str]
    login_password: Optional[str]


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _yaml_bool(data: Dict[str, object], path: str, default: bool) -> bool:
    value = data.get(path)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_text(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _env_optional_bool(name: str) -> Optional[bool]:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return None
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_yaml_config() -> Dict[str, object]:
    config_path = Path(os.environ.get("VW_APPIUM_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))).expanduser()
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _yaml_text(data: Dict[str, object], *path: str) -> Optional[str]:
    current: object = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if current is None:
        return None
    text = str(current).strip()
    return text or None


def _env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value.strip())
    except ValueError:
        return default


def discover_first_online_ios_udid(xctrace_output: str) -> Optional[str]:
    in_devices_section = False
    for raw_line in xctrace_output.splitlines():
        line = raw_line.strip()
        if line == "== Devices ==":
            in_devices_section = True
            continue
        if line.startswith("== ") and line != "== Devices ==":
            in_devices_section = False
        if not in_devices_section or "Mac" in line:
            continue
        match = re.search(r"\(([0-9A-Fa-f]{8}-[0-9A-Fa-f]{16})\)$", line)
        if match:
            return match.group(1)
    return None


def auto_detect_online_ios_udid() -> Optional[str]:
    try:
        result = subprocess.run(
            ["xcrun", "xctrace", "list", "devices"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return discover_first_online_ios_udid(result.stdout)


def load_ios_config() -> IosAppiumConfig:
    yaml_config = _read_yaml_config()
    target = _env_text("VW_IOS_TARGET") or _yaml_text(yaml_config, "target") or "device"
    explicit_udid = _env_text("VW_IOS_UDID")
    target_udid = _yaml_text(yaml_config, target, "udid")
    bundle_id = _env_text("VW_IOS_BUNDLE_ID") or _yaml_text(yaml_config, "bundle_id") or DEFAULT_BUNDLE_ID
    app_path = _env_text("VW_IOS_APP") or _yaml_text(yaml_config, "app_path")
    platform_version = _env_text("VW_IOS_PLATFORM_VERSION") or _yaml_text(yaml_config, target, "platform_version")
    device_name = _env_text("VW_IOS_DEVICE_NAME") or _yaml_text(yaml_config, target, "device_name")
    return IosAppiumConfig(
        target=target,
        server_url=os.environ.get("VW_APPIUM_SERVER_URL", DEFAULT_SERVER_URL).strip() or DEFAULT_SERVER_URL,
        udid=explicit_udid or target_udid or auto_detect_online_ios_udid(),
        bundle_id=bundle_id,
        app_path=app_path,
        artifact_dir=Path(os.environ.get("VW_APPIUM_ARTIFACT_DIR", str(DEFAULT_ARTIFACT_DIR))).expanduser(),
        platform_version=platform_version,
        device_name=device_name,
        xcode_org_id=_env_text("VW_IOS_XCODE_ORG_ID") or _yaml_text(yaml_config, target, "xcode_org_id"),
        xcode_signing_id=_env_text("VW_IOS_XCODE_SIGNING_ID") or _yaml_text(yaml_config, target, "xcode_signing_id"),
        updated_wda_bundle_id=_env_text("VW_IOS_UPDATED_WDA_BUNDLE_ID")
        or _yaml_text(yaml_config, target, "updated_wda_bundle_id"),
        show_xcode_log=_env_bool("VW_IOS_SHOW_XCODE_LOG", _yaml_bool(yaml_config.get(target, {}) if isinstance(yaml_config.get(target), dict) else {}, "show_xcode_log", False)),
        allow_provisioning_device_registration=_env_bool(
            "VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION",
            _yaml_bool(yaml_config.get(target, {}) if isinstance(yaml_config.get(target), dict) else {}, "allow_provisioning_device_registration", False),
        ),
        use_new_wda=_env_bool("VW_IOS_USE_NEW_WDA", _yaml_bool(yaml_config.get(target, {}) if isinstance(yaml_config.get(target), dict) else {}, "use_new_wda", False)),
        use_preinstalled_wda=_env_optional_bool("VW_IOS_USE_PREINSTALLED_WDA")
        if _env_optional_bool("VW_IOS_USE_PREINSTALLED_WDA") is not None
        else (
            _yaml_bool(yaml_config.get(target, {}) if isinstance(yaml_config.get(target), dict) else {}, "use_preinstalled_wda", False)
            if _yaml_text(yaml_config, target, "use_preinstalled_wda") is not None or (
                isinstance(yaml_config.get(target), dict) and "use_preinstalled_wda" in yaml_config.get(target, {})
            )
            else None
        ),
        no_reset=_env_bool("VW_IOS_NO_RESET", _yaml_bool(yaml_config, "no_reset", True)),
        wait_for_idle_timeout=_env_float("VW_IOS_WAIT_FOR_IDLE_TIMEOUT", 1.0),
        reduce_motion=_env_bool("VW_IOS_REDUCE_MOTION", True),
        should_use_singleton_test_manager=_env_optional_bool("VW_IOS_SHOULD_USE_SINGLETON_TEST_MANAGER")
        if _env_optional_bool("VW_IOS_SHOULD_USE_SINGLETON_TEST_MANAGER") is not None
        else (
            _yaml_bool(yaml_config.get(target, {}) if isinstance(yaml_config.get(target), dict) else {}, "should_use_singleton_test_manager", False)
            if _yaml_text(yaml_config, target, "should_use_singleton_test_manager") is not None or (
                isinstance(yaml_config.get(target), dict) and "should_use_singleton_test_manager" in yaml_config.get(target, {})
            )
            else None
        ),
        login_username=_env_text("VW_LOGIN_USERNAME") or _yaml_text(yaml_config, "login", "username"),
        login_password=_env_text("VW_LOGIN_PASSWORD") or _yaml_text(yaml_config, "login", "password"),
    )


def build_ios_capabilities(config: IosAppiumConfig) -> Dict[str, object]:
    if not config.udid:
        raise RuntimeError(
            "No online iOS device was found. Connect and unlock an iPhone, trust this Mac, "
            "then verify it appears under '== Devices ==' in `xcrun xctrace list devices`. "
            "You can also set VW_IOS_UDID explicitly."
        )

    capabilities: Dict[str, object] = {
        "platformName": "iOS",
        "appium:automationName": "XCUITest",
        "appium:udid": config.udid,
        "appium:noReset": config.no_reset,
        "appium:newCommandTimeout": 180,
        "appium:autoAcceptAlerts": True,
        "appium:includeSafariInWebviews": False,
        "appium:useNewWDA": config.use_new_wda,
        "appium:waitForIdleTimeout": config.wait_for_idle_timeout,
        "appium:reduceMotion": config.reduce_motion,
    }
    if config.use_preinstalled_wda is not None:
        capabilities["appium:usePreinstalledWDA"] = config.use_preinstalled_wda

    if config.app_path:
        capabilities["appium:app"] = config.app_path
    else:
        capabilities["appium:bundleId"] = config.bundle_id

    if config.platform_version:
        capabilities["appium:platformVersion"] = config.platform_version
    if config.device_name:
        capabilities["appium:deviceName"] = config.device_name
    if config.xcode_org_id:
        capabilities["appium:xcodeOrgId"] = config.xcode_org_id
    if config.xcode_signing_id:
        capabilities["appium:xcodeSigningId"] = config.xcode_signing_id
    if config.updated_wda_bundle_id:
        capabilities["appium:updatedWDABundleId"] = config.updated_wda_bundle_id
    if config.show_xcode_log:
        capabilities["appium:showXcodeLog"] = True
    if config.allow_provisioning_device_registration:
        capabilities["appium:allowProvisioningDeviceRegistration"] = True
    if config.should_use_singleton_test_manager is not None:
        capabilities["appium:shouldUseSingletonTestManager"] = config.should_use_singleton_test_manager

    return capabilities
