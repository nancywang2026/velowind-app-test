import os
from pathlib import Path
import subprocess
from typing import Optional

from .config import auto_detect_online_ios_udid, load_ios_config


WDA_PROJECT = (
    Path.home()
    / ".appium"
    / "node_modules"
    / "appium-xcuitest-driver"
    / "node_modules"
    / "appium-webdriveragent"
    / "WebDriverAgent.xcodeproj"
)


def _format_config_value(value):
    return value if value else "<not set>"


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def is_wda_startup_error(message: str) -> bool:
    normalized = (message or "").strip()
    return "Unable to launch WebDriverAgent" in normalized or "xcodebuild failed with code 65" in normalized


def _current_appium_server_log_path(config) -> Path:
    return config.artifact_dir / "appium-server.log"


def _recommended_real_device_command(config) -> str:
    values = {
        "VW_IOS_TARGET": config.target or "device",
        "VW_IOS_UDID": config.udid or "<device-udid>",
        "VW_IOS_PLATFORM_VERSION": config.platform_version or "<ios-version>",
        "VW_IOS_DEVICE_NAME": config.device_name or "<device-name>",
        "VW_IOS_XCODE_ORG_ID": config.xcode_org_id or "K2VHBX5KLX",
        "VW_IOS_XCODE_SIGNING_ID": config.xcode_signing_id or "Apple Development",
        "VW_IOS_UPDATED_WDA_BUNDLE_ID": config.updated_wda_bundle_id or "com.velowind.rider.WebDriverAgentRunner",
        "VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION": "true",
        "VW_IOS_SHOW_XCODE_LOG": "true",
        "VW_IOS_SKIP_WDA_PREFLIGHT": "false",
    }
    return " \\\n".join(f"{key}={value}" for key, value in values.items())


def format_wda_startup_error(config, original_error: Exception, diagnostic_path: Optional[Path] = None) -> str:
    lines = [
        "Real-device Appium startup failed before the test body ran.",
        f"Original error: {original_error}",
        "",
        "What we know:",
        f"- Device UDID: {config.udid or '<missing>'}",
        f"- Appium server: {config.server_url}",
        f"- WDA team id: {config.xcode_org_id or '<missing>'}",
        f"- WDA signing id: {config.xcode_signing_id or 'Apple Development'}",
        f"- WDA bundle id: {config.updated_wda_bundle_id or '<missing>'}",
        "",
        "Recommended checks:",
        "1. Unlock the iPhone, keep it on the home screen, and confirm Developer Mode is still enabled.",
        "2. Run the WDA preflight command below to verify build/signing.",
        "3. If preflight passes but pytest still fails, restart the Appium server and rerun the test.",
        f"4. Inspect the Appium server log at: {_current_appium_server_log_path(config)}",
    ]
    if diagnostic_path is not None:
        lines.append(f"5. Review the generated startup diagnostic at: {diagnostic_path}")
    if not config.xcode_org_id or not config.updated_wda_bundle_id:
        lines.extend(
            [
                "",
                "Missing required WDA signing configuration for reliable real-device runs:",
                "- VW_IOS_XCODE_ORG_ID",
                "- VW_IOS_UPDATED_WDA_BUNDLE_ID",
            ]
        )
    lines.extend(
        [
            "",
            "Preflight command:",
            _recommended_real_device_command(config),
            "PYTHONPATH=apps/velowind-app/appium python3 -m velowind_appium.preflight",
        ]
    )
    return "\n".join(lines)


def write_wda_startup_diagnostic(config, original_error: Exception) -> Path:
    diagnostic_path = config.artifact_dir / "wda-startup-diagnostic.txt"
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_path.write_text(format_wda_startup_error(config, original_error), encoding="utf-8")
    return diagnostic_path


def _run_wda_build_preflight(config) -> int:
    if _env_bool("VW_IOS_SKIP_WDA_PREFLIGHT", True):
        print("WDA build preflight: skipped by default to reuse installed WebDriverAgent")
        return 0

    if not config.xcode_org_id or not config.updated_wda_bundle_id:
        print(
            "WDA build preflight: skipped. Set VW_IOS_XCODE_ORG_ID and "
            "VW_IOS_UPDATED_WDA_BUNDLE_ID to validate signing before pytest."
        )
        return 0

    if not WDA_PROJECT.exists():
        print(f"WDA build preflight: skipped. WebDriverAgent project not found at {WDA_PROJECT}")
        return 0

    signing_id = config.xcode_signing_id or "Apple Development"
    command = [
        "xcodebuild",
        "build-for-testing",
        "-project",
        str(WDA_PROJECT),
        "-scheme",
        "WebDriverAgentRunner",
        "-destination",
        f"id={config.udid}",
        f"DEVELOPMENT_TEAM={config.xcode_org_id}",
        f"CODE_SIGN_IDENTITY={signing_id}",
        f"PRODUCT_BUNDLE_IDENTIFIER={config.updated_wda_bundle_id}",
        "GCC_TREAT_WARNINGS_AS_ERRORS=0",
        "COMPILER_INDEX_STORE_ENABLE=NO",
    ]

    if config.platform_version:
        version_parts = config.platform_version.split(".")
        if len(version_parts) >= 2:
            command.append(f"IPHONEOS_DEPLOYMENT_TARGET={version_parts[0]}.{version_parts[1]}")

    if config.allow_provisioning_device_registration:
        command.extend(["-allowProvisioningUpdates", "-allowProvisioningDeviceRegistration"])

    print("WDA build preflight: running xcodebuild build-for-testing...")
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        print("WDA build preflight: passed")
        return 0

    log_path = config.artifact_dir / "wda-preflight-xcodebuild.log"
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    print(f"WDA build preflight: failed with exit code {result.returncode}")
    print(f"WDA xcodebuild log: {log_path}")
    return result.returncode


def main() -> int:
    config = load_ios_config()
    detected_udid = config.udid or auto_detect_online_ios_udid()
    if not detected_udid:
        print(
            "No online iOS device found. Unlock the iPhone, keep it connected, "
            "tap Trust if prompted, then run `xcrun xctrace list devices`."
        )
        return 1

    print(f"Online iOS device UDID: {detected_udid}")
    print(f"Bundle ID: {config.bundle_id}")
    print(f"Appium server: {config.server_url}")
    print(f"WDA Xcode org id: {_format_config_value(config.xcode_org_id)}")
    print(f"WDA signing id: {_format_config_value(config.xcode_signing_id or 'Apple Development')}")
    print(f"WDA bundle id: {_format_config_value(config.updated_wda_bundle_id)}")
    print(f"WDA allow provisioning registration: {config.allow_provisioning_device_registration}")
    return _run_wda_build_preflight(config)


if __name__ == "__main__":
    raise SystemExit(main())
