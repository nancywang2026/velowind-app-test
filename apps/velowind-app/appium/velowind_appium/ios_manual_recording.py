from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from .actions import capture_debug_artifacts
from .artifacts import ensure_artifact_dir, safe_name
from .config import load_ios_config
from .driver import create_ios_driver


DEFAULT_RECORDING_DIR = Path(".tmp/appium-ios/recordings")
DEFAULT_MODULE_DIR = Path("apps/velowind-app/appium/tests/generated")
MAX_SUGGESTIONS = 5


@dataclass(frozen=True)
class RecordingCommand:
    kind: str
    accessibility_id: str | None = None
    text: str | None = None
    value: str | None = None
    direction: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class SnapshotSummary:
    screenshot_path: str | None
    xml_path: str | None
    source_hash: str
    visible_ids: list[str]
    visible_texts: list[str]


@dataclass(frozen=True)
class RecordingStep:
    index: int
    label: str
    command: RecordingCommand
    captured_at: str
    snapshot: SnapshotSummary


def parse_recording_command(raw_command: str) -> RecordingCommand:
    tokens = shlex.split(raw_command)
    if not tokens:
        raise ValueError("Empty command.")

    command = tokens[0].lower()
    if command == "tap":
        if len(tokens) < 2:
            raise ValueError("Usage: tap <accessibility_id> [text]")
        return RecordingCommand(
            kind="tap",
            accessibility_id=tokens[1],
            text=" ".join(tokens[2:]) or None,
        )
    if command == "tap_text":
        if len(tokens) < 2:
            raise ValueError("Usage: tap_text <text>")
        return RecordingCommand(kind="tap_text", text=" ".join(tokens[1:]))
    if command == "input":
        if len(tokens) < 3:
            raise ValueError("Usage: input <accessibility_id> <value>")
        return RecordingCommand(
            kind="input",
            accessibility_id=tokens[1],
            value=" ".join(tokens[2:]),
        )
    if command == "back":
        return RecordingCommand(kind="back")
    if command == "swipe":
        if len(tokens) != 2 or tokens[1] not in {"up", "down"}:
            raise ValueError("Usage: swipe <up|down>")
        return RecordingCommand(kind="swipe", direction=tokens[1])
    if command == "wait":
        return RecordingCommand(kind="wait", note=" ".join(tokens[1:]) or None)
    if command == "note":
        if len(tokens) < 2:
            raise ValueError("Usage: note <description>")
        return RecordingCommand(kind="note", note=" ".join(tokens[1:]))
    raise ValueError(f"Unsupported command: {tokens[0]}")


def extract_visible_identifiers(page_source: str, limit: int = MAX_SUGGESTIONS) -> tuple[list[str], list[str]]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return [], []

    identifiers: list[str] = []
    texts: list[str] = []

    def append_unique(bucket: list[str], value: str) -> None:
        normalized = value.strip()
        if not normalized:
            return
        if normalized in bucket:
            return
        bucket.append(normalized)

    for element in root.iter():
        visible = str(element.attrib.get("visible", "true")).lower()
        if visible == "false":
            continue

        for key in ("name", "label", "content-desc", "resource-id"):
            value = element.attrib.get(key)
            if value:
                append_unique(identifiers, value)

        for key in ("label", "value", "name", "text"):
            value = element.attrib.get(key)
            if not value:
                continue
            trimmed = value.strip()
            if len(trimmed) > 30:
                continue
            append_unique(texts, trimmed)

        if len(identifiers) >= limit and len(texts) >= limit:
            break

    return identifiers[:limit], texts[:limit]


def capture_snapshot(driver: WebDriver, artifact_dir: Path, label: str) -> SnapshotSummary:
    artifacts = capture_debug_artifacts(driver, artifact_dir, label)
    page_source = ""
    try:
        page_source = driver.page_source
    except WebDriverException:
        page_source = ""

    visible_ids, visible_texts = extract_visible_identifiers(page_source)
    return SnapshotSummary(
        screenshot_path=str(artifacts["PNG"]) if "PNG" in artifacts else None,
        xml_path=str(artifacts["XML"]) if "XML" in artifacts else None,
        source_hash=sha1(page_source.encode("utf-8")).hexdigest(),
        visible_ids=visible_ids,
        visible_texts=visible_texts,
    )


def build_recording_payload(
    *,
    session_name: str,
    module_name: str,
    test_name: str,
    output_dir: Path,
    steps: list[RecordingStep],
    config: Any,
) -> dict[str, Any]:
    return {
        "session_name": session_name,
        "module_name": module_name,
        "test_name": test_name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "platform": "ios",
        "bundle_id": config.bundle_id,
        "udid": config.udid,
        "output_dir": str(output_dir),
        "steps": [
            {
                "index": step.index,
                "label": step.label,
                "captured_at": step.captured_at,
                "command": asdict(step.command),
                "snapshot": asdict(step.snapshot),
            }
            for step in steps
        ],
    }


def render_generator_instructions(recording_path: Path) -> str:
    return (
        "录制完成。接下来可以生成测试草稿：\n"
        f"PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.generate_ios_test_from_recording {recording_path}"
    )


def _prompt(message: str) -> str:
    sys.stdout.write(message)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def _default_session_name() -> str:
    return datetime.now().strftime("ios-recording-%Y%m%d-%H%M%S")


def _default_test_name(session_name: str) -> str:
    return f"test_{safe_name(session_name).replace('-', '_')}"


def _default_module_name(session_name: str) -> str:
    return f"test_{safe_name(session_name).replace('-', '_')}.py"


def _step_label(raw_label: str, index: int) -> str:
    return safe_name(raw_label or f"step-{index}")


def record_ios_journey(args: argparse.Namespace) -> int:
    config = load_ios_config()
    session_name = safe_name(args.session_name or _default_session_name())
    test_name = args.test_name or _default_test_name(session_name)
    module_name = args.module_name or _default_module_name(session_name)
    artifact_dir = ensure_artifact_dir(Path(args.output_dir or DEFAULT_RECORDING_DIR) / session_name)
    recording_path = artifact_dir / "recording.json"

    driver = create_ios_driver(config)
    steps: list[RecordingStep] = []
    try:
        print("Recorder 已连接 iPhone。先把 App 切到你要开始的页面。")
        print("每次你在手机上完成一个动作后，在这里输入命令。")
        print("支持命令: tap <id> [text], tap_text <text>, input <id> <value>, back, swipe <up|down>, wait [note], note <text>, done")

        initial_snapshot = capture_snapshot(driver, artifact_dir, "00-initial")
        steps.append(
            RecordingStep(
                index=0,
                label="initial-state",
                command=RecordingCommand(kind="wait", note="initial-state"),
                captured_at=datetime.now().isoformat(timespec="seconds"),
                snapshot=initial_snapshot,
            )
        )

        index = 1
        while True:
            raw_command = _prompt("action> ")
            if not raw_command:
                continue
            if raw_command.lower() in {"done", "exit", "quit"}:
                break

            try:
                command = parse_recording_command(raw_command)
            except ValueError as error:
                print(error)
                continue

            raw_label = _prompt("label> ")
            label = _step_label(raw_label, index)
            snapshot = capture_snapshot(driver, artifact_dir, f"{index:02d}-{label}")
            step = RecordingStep(
                index=index,
                label=label,
                command=command,
                captured_at=datetime.now().isoformat(timespec="seconds"),
                snapshot=snapshot,
            )
            steps.append(step)

            print(
                f"已记录 step {index}: {command.kind} | ids={snapshot.visible_ids[:3]} | texts={snapshot.visible_texts[:3]}"
            )
            index += 1

        payload = build_recording_payload(
            session_name=session_name,
            module_name=module_name,
            test_name=test_name,
            output_dir=artifact_dir,
            steps=steps,
            config=config,
        )
        recording_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"录制结果已保存到 {recording_path}")
        print(render_generator_instructions(recording_path))
        return 0
    finally:
        driver.quit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record manual iPhone app interactions and save a replayable trace.")
    parser.add_argument("--session-name", help="Session name used for artifact and test file names.")
    parser.add_argument("--test-name", help="Pytest test function name to generate later.")
    parser.add_argument("--module-name", help="Target pytest module filename to generate later.")
    parser.add_argument("--output-dir", help="Directory for recording artifacts.", default=str(DEFAULT_RECORDING_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return record_ios_journey(args)


if __name__ == "__main__":
    raise SystemExit(main())
