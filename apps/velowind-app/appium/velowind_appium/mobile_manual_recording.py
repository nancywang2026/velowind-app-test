from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
import json
from pathlib import Path
from typing import Any, Callable

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from .actions import capture_debug_artifacts
from .android_config import load_android_config
from .android_driver import create_android_driver
from .artifacts import ensure_artifact_dir, safe_name
from .bug_recording import (
    BugCapture,
    BugRecording,
    SnapshotSummary,
    apply_review_command,
    build_bug_recording_payload,
    build_capture,
    parse_bug_command,
    render_bug_report,
    render_taiga_issue,
)
from .config import load_ios_config
from .driver import create_ios_driver
from .ios_manual_recording import extract_visible_identifiers


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


def capture_bug_snapshot(driver: WebDriver, artifact_dir: Path, label: str) -> SnapshotSummary:
    capture_error = None
    artifacts = {}
    try:
        artifacts = capture_debug_artifacts(driver, artifact_dir, label)
    except WebDriverException as error:
        capture_error = f"{type(error).__name__}: {error}"

    page_source = ""
    try:
        page_source = driver.page_source
    except WebDriverException as error:
        capture_error = capture_error or f"{type(error).__name__}: {error}"

    if capture_error is None:
        missing_artifacts = [artifact_type for artifact_type in ("PNG", "XML") if artifact_type not in artifacts]
        if missing_artifacts:
            capture_error = f"Missing capture artifacts: {', '.join(missing_artifacts)}"

    visible_ids, visible_texts = extract_visible_identifiers(page_source)
    return SnapshotSummary(
        screenshot_path=str(artifacts["PNG"]) if "PNG" in artifacts else None,
        xml_path=str(artifacts["XML"]) if "XML" in artifacts else None,
        source_hash=sha1(page_source.encode("utf-8")).hexdigest(),
        visible_ids=visible_ids,
        visible_texts=visible_texts,
        capture_error=capture_error,
    )


def write_bug_recording_outputs(recording: BugRecording, artifact_dir: Path) -> dict[str, Path]:
    ensure_artifact_dir(artifact_dir)
    recording_path = artifact_dir / "recording.json"
    bug_report_path = artifact_dir / "bug-report.md"
    taiga_issue_path = artifact_dir / "taiga-issue.md"

    payload = build_bug_recording_payload(recording, artifact_dir)
    recording_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    bug_report_path.write_text(render_bug_report(recording, recording_path), encoding="utf-8")
    taiga_issue_path.write_text(render_taiga_issue(recording, bug_report_path), encoding="utf-8")
    return {"recording": recording_path, "bug_report": bug_report_path, "taiga_issue": taiga_issue_path}


def _prompt(message: str) -> str | None:
    import sys

    sys.stdout.write(message)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        return None
    return line.strip()


def _default_session_name(platform: str) -> str:
    return f"{platform}-bug-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _review_recording(recording: BugRecording) -> BugRecording:
    current = recording
    while True:
        print("Captured steps:")
        for capture in current.captures:
            print(f"{capture.index}. {capture.description}")
        raw_command = _prompt("review> ")
        if raw_command is None:
            return current
        if not raw_command or raw_command == "keep":
            return current
        try:
            current = apply_review_command(current, raw_command)
        except (ValueError, IndexError) as error:
            print(error)


def record_bug_journey(args: argparse.Namespace, runtime: PlatformRuntime) -> int:
    config = runtime.load_config()
    artifact_root = Path(args.output_dir).expanduser() if args.output_dir else default_recording_dir(runtime.platform)
    session_name = safe_name(args.session_name or _default_session_name(runtime.platform))
    artifact_dir = ensure_artifact_dir(artifact_root / session_name)
    environment = build_environment_metadata(runtime.platform, config)

    driver = runtime.create_driver(config)
    captures: list[BugCapture] = []
    expected_result = ""
    actual_result = ""
    notes: list[str] = []
    try:
        print(f"Recorder connected for {runtime.platform}. Use capture, actual, expected, note, done.")
        initial_snapshot = capture_bug_snapshot(driver, artifact_dir, "00-initial")
        captures.append(build_capture(0, "初始页面", initial_snapshot))

        while True:
            raw_command = _prompt("bug> ")
            if raw_command is None:
                break
            try:
                command = parse_bug_command(raw_command)
            except ValueError as error:
                print(error)
                continue

            if command.kind == "done":
                break
            if command.kind == "expected":
                expected_result = command.text or ""
                continue
            if command.kind == "actual":
                actual_result = command.text or ""
                continue
            if command.kind == "note":
                if command.text:
                    notes.append(command.text)
                continue
            if command.kind == "capture":
                index = len(captures)
                snapshot = capture_bug_snapshot(driver, artifact_dir, f"{index:02d}-{safe_name(command.text or 'capture')}")
                capture = build_capture(index, command.text, snapshot)
                captures.append(capture)
                print(f"Captured {capture.index}: {capture.description}")

        title = actual_result or args.session_name or session_name
        recording = BugRecording(
            session_name=session_name,
            platform=runtime.platform,
            title=title,
            environment=environment,
            expected_result=expected_result,
            actual_result=actual_result,
            notes=notes,
            captures=captures,
        )
        reviewed = _review_recording(recording)
        paths = write_bug_recording_outputs(reviewed, artifact_dir)
        print(f"Bug report written: {paths['bug_report']}")
        print(f"Taiga issue draft written: {paths['taiga_issue']}")
        return 0
    finally:
        driver.quit()


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
    parser.add_argument("--taiga-project", help="Taiga project slug or identifier for bug report handoff.")
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
        return record_bug_journey(args, runtime)

    if runtime.platform == "ios":
        from .ios_manual_recording import record_ios_journey

        return record_ios_journey(args)

    parser.error("Android manual recording is not available yet; use --mode bug.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
