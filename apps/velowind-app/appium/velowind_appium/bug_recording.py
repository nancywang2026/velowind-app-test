from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
import shlex
from typing import Any

from .artifacts import safe_name


_REVIEW_USAGE = "Usage: keep | no-op | rename <index> <text> | delete <index>"


@dataclass(frozen=True)
class BugCommand:
    kind: str
    text: str | None = None


@dataclass(frozen=True)
class SnapshotSummary:
    screenshot_path: str | None
    xml_path: str | None
    source_hash: str
    visible_ids: list[str]
    visible_texts: list[str]
    capture_error: str | None = None


@dataclass(frozen=True)
class BugCapture:
    index: int
    label: str
    description: str
    user_description: str | None
    captured_at: str
    snapshot: SnapshotSummary


@dataclass(frozen=True)
class BugRecording:
    session_name: str
    platform: str
    title: str
    environment: dict[str, Any]
    expected_result: str
    actual_result: str
    notes: list[str]
    captures: list[BugCapture]


def parse_bug_command(raw_command: str) -> BugCommand:
    normalized = raw_command.strip()
    if not normalized:
        return BugCommand(kind="capture")

    tokens = shlex.split(normalized)
    command = tokens[0].lower()
    text = normalized[len(tokens[0]) :].strip() or None

    if command in {"capture", "actual", "expected", "note"}:
        return BugCommand(kind=command, text=text)
    if command in {"done", "exit", "quit"}:
        return BugCommand(kind="done")
    raise ValueError(f"Unsupported bug recording command: {tokens[0]}")


def generated_step_description(snapshot: SnapshotSummary) -> str:
    visible_texts = [value.strip() for value in snapshot.visible_texts if value.strip()]
    if visible_texts:
        return " / ".join(visible_texts[:2])

    visible_ids = [value.strip() for value in snapshot.visible_ids if value.strip()]
    if visible_ids:
        return " / ".join(visible_ids[:2])

    return "记录当前页面状态"


def build_capture(index: int, user_text: str | None, snapshot: SnapshotSummary) -> BugCapture:
    description = user_text or generated_step_description(snapshot)
    return BugCapture(
        index=index,
        label=safe_name(description),
        description=description,
        user_description=user_text,
        captured_at=datetime.now().isoformat(timespec="seconds"),
        snapshot=snapshot,
    )


def apply_review_command(recording: BugRecording, raw_command: str) -> BugRecording:
    normalized = raw_command.strip()
    if not normalized or normalized.lower() in {"keep", "noop", "no-op"}:
        return recording

    tokens = normalized.split(maxsplit=2)
    command = tokens[0].lower()

    if command == "rename" and len(tokens) == 3:
        target = _parse_review_index(tokens[1])
        if not any(capture.index == target for capture in recording.captures):
            raise ValueError(f"No capture found with index {target}")
        updated = [
            replace(capture, label=safe_name(tokens[2]), description=tokens[2], user_description=tokens[2])
            if capture.index == target
            else capture
            for capture in recording.captures
        ]
        return replace(recording, captures=updated)

    if command == "delete" and len(tokens) == 2:
        target = _parse_review_index(tokens[1])
        if not any(capture.index == target for capture in recording.captures):
            raise ValueError(f"No capture found with index {target}")
        remaining = [capture for capture in recording.captures if capture.index != target]
        reindexed = [replace(capture, index=index) for index, capture in enumerate(remaining, start=1)]
        return replace(recording, captures=reindexed)

    raise ValueError(_REVIEW_USAGE)


def build_bug_recording_payload(recording: BugRecording, output_dir: Path) -> dict[str, Any]:
    return {
        "mode": "bug",
        "session_name": recording.session_name,
        "platform": recording.platform,
        "title": recording.title,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "output_dir": str(output_dir),
        "environment": recording.environment,
        "expected_result": recording.expected_result,
        "actual_result": recording.actual_result,
        "notes": list(recording.notes),
        "steps": [asdict(capture) for capture in recording.captures],
    }


def render_bug_report(recording: BugRecording, recording_path: Path) -> str:
    evidence_lines = _evidence_lines(recording.captures)
    notes = recording.notes or ["无"]

    return "\n".join(
        [
            f"# {recording.title}",
            "",
            f"Session: `{recording.session_name}`",
            "",
            "## Environment",
            f"- Platform: {_platform_label(recording.platform)}",
            *_environment_lines(recording.environment),
            "",
            "## Reproduction Steps",
            *_step_lines(recording.captures),
            "",
            "## Expected Result",
            recording.expected_result or "未填写",
            "",
            "## Actual Result",
            recording.actual_result or "未填写",
            "",
            "## Notes",
            *[f"- {note}" for note in notes],
            "",
            "## Evidence",
            *evidence_lines,
            "",
            "## Raw Recording",
            str(recording_path),
            "",
        ]
    )


def render_taiga_issue(recording: BugRecording, bug_report_path: Path) -> str:
    evidence_lines = _taiga_evidence_lines(recording.captures)

    return "\n".join(
        [
            "## 平台",
            _platform_label(recording.platform),
            "",
            "## 复现步骤",
            *_step_lines(recording.captures),
            "",
            "## 期望结果",
            recording.expected_result or "未填写",
            "",
            "## 实际结果",
            recording.actual_result or "未填写",
            "",
            "## 证据",
            *evidence_lines,
            "",
            "## 本地报告",
            str(bug_report_path),
            "",
        ]
    )


def _platform_label(platform: str) -> str:
    normalized = platform.lower()
    if normalized == "ios":
        return "iOS"
    if normalized == "android":
        return "Android"
    return platform


def _parse_review_index(raw_index: str) -> int:
    try:
        return int(raw_index)
    except ValueError as exc:
        raise ValueError(_REVIEW_USAGE) from exc


def _environment_lines(environment: dict[str, Any]) -> list[str]:
    return [
        f"- `{key}`: `{value}`"
        for key, value in environment.items()
        if value is not None and value != ""
    ]


def _step_lines(captures: list[BugCapture]) -> list[str]:
    return [f"{capture.index}. {capture.description}" for capture in captures] or ["1. 未记录复现步骤"]


def _evidence_lines(captures: list[BugCapture]) -> list[str]:
    lines = []
    previous_hash = None
    for capture in captures:
        repeated = " (same page source as previous capture)" if capture.snapshot.source_hash == previous_hash else ""
        lines.append(f"- Step {capture.index}: {capture.description}{repeated}")
        if capture.snapshot.screenshot_path:
            lines.append(f"  - Screenshot: {capture.snapshot.screenshot_path}")
        if capture.snapshot.xml_path:
            lines.append(f"  - XML: {capture.snapshot.xml_path}")
        if capture.snapshot.capture_error:
            lines.append(f"  - Capture error: {capture.snapshot.capture_error}")
        previous_hash = capture.snapshot.source_hash
    return lines or ["- 未生成证据"]


def _taiga_evidence_lines(captures: list[BugCapture]) -> list[str]:
    lines = []
    for capture in captures:
        if capture.snapshot.screenshot_path:
            lines.append(f"- Step {capture.index} screenshot: {capture.snapshot.screenshot_path}")
        if capture.snapshot.xml_path:
            lines.append(f"- Step {capture.index} XML: {capture.snapshot.xml_path}")
    return lines or ["- 未生成证据"]
