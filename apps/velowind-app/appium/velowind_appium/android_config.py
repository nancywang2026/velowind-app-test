from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Dict, Optional

import yaml


DEFAULT_SERVER_URL = "http://127.0.0.1:4724"
DEFAULT_APP_PACKAGE = "com.velowind.rider"
DEFAULT_DEVICE_NAME = "Android Emulator"
DEFAULT_ARTIFACT_DIR = Path(".tmp/appium-android")
DEFAULT_CONFIG_FILE = Path(__file__).resolve().parents[1] / "android-appium.yaml"
DEFAULT_TARGET = "android_studio"


@dataclass(frozen=True)
class AndroidAppiumConfig:
    target: str
    server_url: str
    udid: Optional[str]
    device_name: Optional[str]
    app_path: Optional[str]
    app_package: str
    app_activity: Optional[str]
    artifact_dir: Path
    platform_version: Optional[str]
    no_reset: bool
    auto_grant_permissions: bool
    skip_device_initialization: bool
    login_username: Optional[str]
    login_password: Optional[str]


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_text(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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


def _yaml_bool(data: Dict[str, object], path: str, default: bool) -> bool:
    value = data.get(path)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _yaml_target_bool(data: Dict[str, object], target: str, path: str, default: bool) -> bool:
    target_config = data.get(target)
    if not isinstance(target_config, dict):
        return default
    return _yaml_bool(target_config, path, default)


def _online_android_udids(adb_devices_output: str) -> list[str]:
    udids: list[str] = []
    for raw_line in adb_devices_output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        udid, state = parts[0], parts[1]
        if state == "device":
            udids.append(udid)
    return udids


def discover_first_online_android_udid(adb_devices_output: str) -> Optional[str]:
    udids = _online_android_udids(adb_devices_output)
    return udids[0] if udids else None


def discover_first_online_android_udid_for_target(adb_devices_output: str, target: str) -> Optional[str]:
    udids = _online_android_udids(adb_devices_output)
    if target == "android_studio":
        return next((udid for udid in udids if udid.startswith("emulator-")), None)
    if target == "physical":
        return next((udid for udid in udids if not udid.startswith("emulator-") and ":" not in udid), None)
    if target == "mumu":
        return next((udid for udid in udids if ":" in udid), None)
    return udids[0] if udids else None


def auto_detect_online_android_udid(target: Optional[str] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            ["adb", "devices"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if target:
        return discover_first_online_android_udid_for_target(result.stdout, target)
    return discover_first_online_android_udid(result.stdout)


def load_android_config() -> AndroidAppiumConfig:
    yaml_config = _read_yaml_config()
    target = _env_text("VW_ANDROID_TARGET") or _yaml_text(yaml_config, "target") or DEFAULT_TARGET
    explicit_udid = _env_text("VW_ANDROID_UDID")
    target_udid = _yaml_text(yaml_config, target, "udid")

    return AndroidAppiumConfig(
        target=target,
        server_url=os.environ.get("VW_APPIUM_SERVER_URL", DEFAULT_SERVER_URL).strip() or DEFAULT_SERVER_URL,
        udid=explicit_udid or target_udid or auto_detect_online_android_udid(target),
        device_name=_env_text("VW_ANDROID_DEVICE_NAME")
        or _yaml_text(yaml_config, target, "device_name")
        or DEFAULT_DEVICE_NAME,
        app_path=_env_text("VW_ANDROID_APP") or _yaml_text(yaml_config, target, "app_path") or _yaml_text(yaml_config, "app_path"),
        app_package=_env_text("VW_ANDROID_APP_PACKAGE") or _yaml_text(yaml_config, "app_package") or DEFAULT_APP_PACKAGE,
        app_activity=_env_text("VW_ANDROID_APP_ACTIVITY") or _yaml_text(yaml_config, "app_activity"),
        artifact_dir=Path(os.environ.get("VW_APPIUM_ARTIFACT_DIR", str(DEFAULT_ARTIFACT_DIR))).expanduser(),
        platform_version=_env_text("VW_ANDROID_PLATFORM_VERSION") or _yaml_text(yaml_config, target, "platform_version"),
        no_reset=_env_bool("VW_ANDROID_NO_RESET", _yaml_bool(yaml_config, "no_reset", True)),
        auto_grant_permissions=_env_bool(
            "VW_ANDROID_AUTO_GRANT_PERMISSIONS",
            _yaml_bool(yaml_config, "auto_grant_permissions", True),
        ),
        skip_device_initialization=_env_bool(
            "VW_ANDROID_SKIP_DEVICE_INITIALIZATION",
            _yaml_target_bool(
                yaml_config,
                target,
                "skip_device_initialization",
                _yaml_bool(yaml_config, "skip_device_initialization", False),
            ),
        ),
        login_username=_env_text("VW_LOGIN_USERNAME") or _yaml_text(yaml_config, "login", "username"),
        login_password=_env_text("VW_LOGIN_PASSWORD") or _yaml_text(yaml_config, "login", "password"),
    )


def build_android_capabilities(config: AndroidAppiumConfig) -> Dict[str, object]:
    if not config.udid:
        raise RuntimeError(
            "No online Android device was found. Start a device or emulator, verify it appears as `device` "
            "in `adb devices`, or set VW_ANDROID_UDID explicitly."
        )

    capabilities: Dict[str, object] = {
        "platformName": "Android",
        "appium:automationName": "UiAutomator2",
        "appium:udid": config.udid,
        "appium:deviceName": config.device_name or DEFAULT_DEVICE_NAME,
        "appium:noReset": config.no_reset,
        "appium:forceAppLaunch": True,
        "appium:autoGrantPermissions": config.auto_grant_permissions,
        "appium:newCommandTimeout": 180,
    }
    if config.skip_device_initialization:
        capabilities["appium:skipDeviceInitialization"] = True

    if config.platform_version:
        capabilities["appium:platformVersion"] = config.platform_version

    if config.app_path:
        capabilities["appium:app"] = config.app_path
        if config.app_package:
            capabilities["appium:appPackage"] = config.app_package
        if config.app_activity:
            capabilities["appium:appActivity"] = config.app_activity
        return capabilities

    if not config.app_package:
        raise RuntimeError("VW_ANDROID_APP_PACKAGE is required when VW_ANDROID_APP is not set.")
    if not config.app_activity:
        raise RuntimeError("VW_ANDROID_APP_ACTIVITY is required when VW_ANDROID_APP is not set.")

    capabilities["appium:appPackage"] = config.app_package
    capabilities["appium:appActivity"] = config.app_activity
    return capabilities
