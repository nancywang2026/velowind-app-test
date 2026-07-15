import shutil
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .android_config import AndroidAppiumConfig, load_android_config


def _format_config_value(value):
    return value if value else "<not set>"


def discover_online_android_udids(adb_devices_output: str) -> list[str]:
    udids: list[str] = []
    for raw_line in adb_devices_output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        udid, state = parts[0], parts[1]
        if udid.startswith("emulator-") and state == "device":
            udids.append(udid)
    return udids


def _validate_app_inputs(config: AndroidAppiumConfig) -> list[str]:
    errors: list[str] = []
    if config.app_path:
        app_path = Path(config.app_path).expanduser()
        if not app_path.exists():
            errors.append(f"APK file does not exist: {app_path}")
        return errors

    if not config.app_package:
        errors.append("VW_ANDROID_APP_PACKAGE is required when VW_ANDROID_APP is not set.")
    if not config.app_activity:
        errors.append("VW_ANDROID_APP_ACTIVITY is required when VW_ANDROID_APP is not set.")
    return errors


def _adb_devices_output() -> str:
    result = subprocess.run(["adb", "devices"], check=False, capture_output=True, text=True, timeout=20)
    return result.stdout


def _appium_server_is_reachable(server_url: str) -> bool:
    status_url = server_url.rstrip("/") + "/status"
    try:
        with urlopen(status_url, timeout=3) as response:
            return 200 <= response.status < 500
    except (OSError, URLError):
        return False


def _uiautomator2_driver_is_installed() -> bool:
    appium_bin = shutil.which("appium")
    if appium_bin is None:
        return False
    result = subprocess.run(
        [appium_bin, "driver", "list", "--installed"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    return "uiautomator2" in output


def main() -> int:
    config = load_android_config()
    errors: list[str] = []

    if shutil.which("adb") is None:
        errors.append("adb not found. Install Android platform-tools and ensure `adb` is on PATH.")
        online_udids: list[str] = []
    else:
        online_udids = discover_online_android_udids(_adb_devices_output())
        if config.udid and config.udid not in online_udids:
            errors.append(f"Configured Android emulator is not online: {config.udid}")
        if not config.udid and not online_udids:
            errors.append("No online Android emulator found. Start an emulator and verify `adb devices`.")

    if not _appium_server_is_reachable(config.server_url):
        errors.append(f"Appium server is not reachable: {config.server_url}")

    if not _uiautomator2_driver_is_installed():
        errors.append("Appium UiAutomator2 driver is not installed. Run `appium driver install uiautomator2`.")

    errors.extend(_validate_app_inputs(config))

    print(f"Android target: {config.target}")
    print(f"Android UDID: {_format_config_value(config.udid or (online_udids[0] if online_udids else None))}")
    print(f"Device name: {_format_config_value(config.device_name)}")
    print(f"Appium server: {config.server_url}")
    print(f"APK path: {_format_config_value(config.app_path)}")
    print(f"App package: {_format_config_value(config.app_package)}")
    print(f"App activity: {_format_config_value(config.app_activity)}")
    print(f"Artifact dir: {config.artifact_dir}")

    if errors:
        print("")
        print("Android Appium preflight failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Android Appium preflight: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
