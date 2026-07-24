from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from appium.webdriver.webdriver import WebDriver

from .android_config import load_android_config
from .android_driver import create_android_driver
from .config import load_ios_config
from .driver import create_ios_driver


DEFAULT_RECORDING_DIRS = {
    "ios": Path(".tmp/appium-ios/recordings"),
    "android": Path(".tmp/appium-android/recordings"),
}
DEFAULT_MODULE_DIR = Path("apps/velowind-app/appium/tests/generated")


@dataclass(frozen=True)
class PlatformRuntime:
    platform: str
    load_config: Callable[[], Any]
    create_driver: Callable[[Any], WebDriver]


def default_recording_dir(platform: str) -> Path:
    normalized = platform.lower()
    try:
        return DEFAULT_RECORDING_DIRS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported platform: {platform}") from exc


def resolve_platform_runtime(platform: str) -> PlatformRuntime:
    normalized = platform.lower()
    if normalized == "ios":
        return PlatformRuntime(platform="ios", load_config=load_ios_config, create_driver=create_ios_driver)
    if normalized == "android":
        return PlatformRuntime(platform="android", load_config=load_android_config, create_driver=create_android_driver)
    raise ValueError(f"Unsupported platform: {platform}")


def build_environment_metadata(platform: str, config: Any) -> dict[str, Any]:
    normalized = platform.lower()
    common = {
        "platform": normalized,
        "server_url": getattr(config, "server_url", None),
        "udid": getattr(config, "udid", None),
        "device_name": getattr(config, "device_name", None),
        "artifact_dir": str(getattr(config, "artifact_dir", "")),
        "platform_version": getattr(config, "platform_version", None),
        "login_username_present": bool(getattr(config, "login_username", None)),
    }

    if normalized == "ios":
        return {
            **common,
            "target": getattr(config, "target", None),
            "bundle_id": getattr(config, "bundle_id", None),
            "app_path": getattr(config, "app_path", None),
        }
    if normalized == "android":
        return {
            **common,
            "target": getattr(config, "target", None),
            "app_package": getattr(config, "app_package", None),
            "app_activity": getattr(config, "app_activity", None),
            "app_path": getattr(config, "app_path", None),
        }
    raise ValueError(f"Unsupported platform: {platform}")


def build_parser(default_platform: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record manual mobile app interactions and bug evidence.")
    parser.add_argument(
        "--platform",
        choices=("ios", "android"),
        default=default_platform,
        required=default_platform is None,
        help="Mobile platform to record.",
    )
    parser.add_argument(
        "--mode",
        choices=("manual", "bug"),
        default="manual",
        help="Recording mode. Android currently supports bug mode only.",
    )
    parser.add_argument("--session-name", help="Session name used for artifact and test file names.")
    parser.add_argument("--test-name", help="Pytest test function name to generate later.")
    parser.add_argument("--module-name", help="Target pytest module filename to generate later.")
    parser.add_argument(
        "--output-dir",
        help="Directory for recording artifacts. Defaults to a platform-specific .tmp directory.",
    )
    return parser


def main(argv: list[str] | None = None, *, default_platform: str | None = None) -> int:
    parser = build_parser(default_platform=default_platform)
    args = parser.parse_args(argv)

    if not args.platform:
        parser.error("--platform is required")

    try:
        runtime = resolve_platform_runtime(args.platform)
    except ValueError as exc:
        parser.error(str(exc))

    if args.output_dir is None:
        args.output_dir = str(default_recording_dir(runtime.platform))

    if args.mode == "bug":
        from .bug_recording import parse_bug_command

        parse_bug_command("capture")
        print(f"{runtime.platform} bug recording mode is wired; capture loop will be added in Task 3.")
        return 0

    if runtime.platform == "ios":
        from .ios_manual_recording import record_ios_journey

        return record_ios_journey(args)

    parser.error("Android manual recording is not available yet; use --mode bug.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
