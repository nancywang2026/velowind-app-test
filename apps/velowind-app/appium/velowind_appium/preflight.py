from pathlib import Path
import os
import subprocess

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


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _run_wda_build_preflight(config) -> int:
    if _env_bool("VW_IOS_SKIP_WDA_PREFLIGHT"):
        print("WDA build preflight: skipped by VW_IOS_SKIP_WDA_PREFLIGHT=true")
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
