from pathlib import Path

from velowind_appium.android_preflight import (
    _validate_app_inputs,
    discover_online_android_udids,
)
from velowind_appium.android_config import AndroidAppiumConfig


def _config(**overrides):
    values = {
        "target": "emulator",
        "server_url": "http://127.0.0.1:4723",
        "udid": "emulator-5554",
        "device_name": "Android Emulator",
        "app_path": None,
        "app_package": "com.velowind.rider",
        "app_activity": ".MainActivity",
        "artifact_dir": Path(".tmp/appium-android"),
        "platform_version": None,
        "no_reset": True,
        "auto_grant_permissions": True,
        "login_username": None,
        "login_password": None,
    }
    values.update(overrides)
    return AndroidAppiumConfig(**values)


def test_discover_online_android_udids_returns_only_online_emulators():
    adb_output = """
List of devices attached
emulator-5554	device
emulator-5556	offline
R5CN12345	device
emulator-5558	device
"""

    assert discover_online_android_udids(adb_output) == ["emulator-5554", "emulator-5558"]


def test_validate_app_inputs_accepts_existing_apk(tmp_path):
    apk = tmp_path / "velowind.apk"
    apk.write_text("apk", encoding="utf-8")

    assert _validate_app_inputs(_config(app_path=str(apk), app_activity=None)) == []


def test_validate_app_inputs_reports_missing_apk():
    errors = _validate_app_inputs(_config(app_path="/tmp/missing-velowind.apk"))

    assert any("APK file does not exist" in error for error in errors)


def test_validate_app_inputs_requires_activity_without_apk():
    errors = _validate_app_inputs(_config(app_path=None, app_activity=None))

    assert any("VW_ANDROID_APP_ACTIVITY" in error for error in errors)
