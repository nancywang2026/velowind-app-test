from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import Dict, Optional


DEFAULT_SERVER_URL = "http://127.0.0.1:4723"
DEFAULT_BUNDLE_ID = "com.velowind.rider"
DEFAULT_ARTIFACT_DIR = Path(".tmp/appium-ios")


@dataclass(frozen=True)
class IosAppiumConfig:
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
    no_reset: bool
    wait_for_idle_timeout: float
    reduce_motion: bool


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
    explicit_udid = _env_text("VW_IOS_UDID")
    return IosAppiumConfig(
        server_url=os.environ.get("VW_APPIUM_SERVER_URL", DEFAULT_SERVER_URL).strip() or DEFAULT_SERVER_URL,
        udid=explicit_udid or auto_detect_online_ios_udid(),
        bundle_id=os.environ.get("VW_IOS_BUNDLE_ID", DEFAULT_BUNDLE_ID).strip() or DEFAULT_BUNDLE_ID,
        app_path=_env_text("VW_IOS_APP"),
        artifact_dir=Path(os.environ.get("VW_APPIUM_ARTIFACT_DIR", str(DEFAULT_ARTIFACT_DIR))).expanduser(),
        platform_version=_env_text("VW_IOS_PLATFORM_VERSION"),
        device_name=_env_text("VW_IOS_DEVICE_NAME"),
        xcode_org_id=_env_text("VW_IOS_XCODE_ORG_ID"),
        xcode_signing_id=_env_text("VW_IOS_XCODE_SIGNING_ID"),
        updated_wda_bundle_id=_env_text("VW_IOS_UPDATED_WDA_BUNDLE_ID"),
        show_xcode_log=_env_bool("VW_IOS_SHOW_XCODE_LOG", False),
        allow_provisioning_device_registration=_env_bool(
            "VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION",
            False,
        ),
        use_new_wda=_env_bool("VW_IOS_USE_NEW_WDA", False),
        no_reset=_env_bool("VW_IOS_NO_RESET", True),
        wait_for_idle_timeout=_env_float("VW_IOS_WAIT_FOR_IDLE_TIMEOUT", 1.0),
        reduce_motion=_env_bool("VW_IOS_REDUCE_MOTION", True),
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

    return capabilities
