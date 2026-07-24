# Appium Bug Recording Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform Appium bug recorder that captures meaningful iOS/Android screen states, generates a reviewable bug report first, and only then offers generated pytest script creation.

**Architecture:** Keep the existing iOS manual recorder compatible, but move shared logic into platform-neutral modules. `mobile_manual_recording.py` owns CLI dispatch and driver lifecycle, `bug_recording.py` owns bug-mode commands/payloads/reports, and existing platform config/driver factories provide iOS/Android differences.

**Tech Stack:** Python 3, Appium Python Client, pytest, existing `velowind_appium` helpers, pnpm scripts, local Markdown artifacts, Taiga MCP via Codex after local report generation.

---

## File Structure

- Create `apps/velowind-app/appium/velowind_appium/bug_recording.py`: bug-mode command parsing, step/review models, description generation, report rendering, and JSON payload building.
- Create `apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py`: shared CLI for `--platform ios|android`, mode dispatch, platform config/driver creation, capture loop, review loop, file writes, optional script-generation prompt.
- Modify `apps/velowind-app/appium/velowind_appium/ios_manual_recording.py`: keep current imports/API usable, but delegate the CLI entry point to `mobile_manual_recording.main(default_platform="ios")`; retain existing action-command functions during migration.
- Modify `apps/velowind-app/appium/velowind_appium/generate_ios_test_from_recording.py`: read reviewed bug-mode steps when present and skip test generation for Android with a clear message until Android generation is implemented.
- Modify `package.json`: add `appium:android:record`; point iOS record command at the shared recorder with `--platform ios`.
- Modify `docs/ios-manual-recording.md`: generalize docs to Appium bug recording and include Android examples.
- Test in `apps/velowind-app/appium/tests/unit-test/test_bug_recording.py`: command parsing, description generation, review mutations, report rendering, payload shape.
- Test in `apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py`: platform dispatch, environment metadata, CLI mode dispatch without starting Appium.
- Extend `apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py`: ensure legacy iOS command parsing/generation behavior still works.

### Task 1: Bug Recording Core

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/bug_recording.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_bug_recording.py`

- [ ] **Step 1: Write failing tests for bug commands, generated descriptions, review commands, and Markdown rendering**

Add this test file:

```python
from pathlib import Path

from velowind_appium.bug_recording import (
    BugCapture,
    BugCommand,
    BugRecording,
    SnapshotSummary,
    apply_review_command,
    build_bug_recording_payload,
    generated_step_description,
    parse_bug_command,
    render_bug_report,
    render_taiga_issue,
)


def test_parse_bug_commands():
    assert parse_bug_command("") == BugCommand(kind="capture", text=None)
    assert parse_bug_command("capture 打开搜索页") == BugCommand(kind="capture", text="打开搜索页")
    assert parse_bug_command("actual 页面一直加载中") == BugCommand(kind="actual", text="页面一直加载中")
    assert parse_bug_command("expected 应展示搜索结果") == BugCommand(kind="expected", text="应展示搜索结果")
    assert parse_bug_command("note 第二次复跑通过") == BugCommand(kind="note", text="第二次复跑通过")
    assert parse_bug_command("done") == BugCommand(kind="done", text=None)


def test_generated_step_description_prefers_short_visible_text():
    snapshot = SnapshotSummary(
        screenshot_path="/tmp/step.png",
        xml_path="/tmp/step.xml",
        source_hash="abc",
        visible_ids=["search-input", "submit-button"],
        visible_texts=["搜索", "正在加载真实搜索结果"],
        capture_error=None,
    )

    assert generated_step_description(snapshot) == "搜索 / 正在加载真实搜索结果"


def test_apply_review_command_renames_and_deletes_steps():
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="search-loading",
        environment={"platform": "ios"},
        expected_result="",
        actual_result="",
        notes=[],
        captures=[
            BugCapture(1, "open-search", "打开搜索页", None, "2026-07-24T10:00:00", SnapshotSummary(None, None, "a", [], [], None)),
            BugCapture(2, "loading", "页面加载", None, "2026-07-24T10:01:00", SnapshotSummary(None, None, "b", [], [], None)),
        ],
    )

    renamed = apply_review_command(recording, "rename 2 搜索结果持续加载不结束")
    assert renamed.captures[1].user_description == "搜索结果持续加载不结束"

    deleted = apply_review_command(renamed, "delete 1")
    assert [capture.index for capture in deleted.captures] == [1]
    assert deleted.captures[0].description == "搜索结果持续加载不结束"


def test_render_bug_report_and_taiga_issue_include_platform_and_evidence():
    recording = BugRecording(
        session_name="search-loading",
        platform="android",
        title="搜索结果持续加载",
        environment={"platform": "android", "app_package": "com.velowind.rider", "udid": "emulator-5554"},
        expected_result="应展示搜索结果或错误态",
        actual_result="页面一直加载中",
        notes=["第二次复跑通过"],
        captures=[
            BugCapture(1, "open-search", "打开搜索页", None, "2026-07-24T10:00:00", SnapshotSummary("/tmp/1.png", "/tmp/1.xml", "a", ["search-input"], ["搜索"], None)),
        ],
    )

    report = render_bug_report(recording, Path("/tmp/recording.json"))
    taiga = render_taiga_issue(recording, Path("/tmp/bug-report.md"))

    assert "Android" in report
    assert "com.velowind.rider" in report
    assert "/tmp/1.png" in report
    assert "页面一直加载中" in taiga
    assert "/tmp/bug-report.md" in taiga


def test_build_bug_recording_payload_is_json_ready():
    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="搜索结果持续加载",
        environment={"platform": "ios", "bundle_id": "com.velowind.rider"},
        expected_result="期望",
        actual_result="实际",
        notes=[],
        captures=[],
    )

    payload = build_bug_recording_payload(recording, output_dir=Path(".tmp/appium-ios/recordings/search-loading"))

    assert payload["mode"] == "bug"
    assert payload["platform"] == "ios"
    assert payload["environment"]["bundle_id"] == "com.velowind.rider"
    assert payload["steps"] == []
```

- [ ] **Step 2: Run the focused tests and verify they fail because the module does not exist**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_bug_recording.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'velowind_appium.bug_recording'`.

- [ ] **Step 3: Implement `bug_recording.py` with the exact public functions used by the tests**

Create `apps/velowind-app/appium/velowind_appium/bug_recording.py` with these exports:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
import shlex
from typing import Any

from .artifacts import safe_name


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
    text = normalized[len(tokens[0]):].strip() or None
    if command in {"capture", "actual", "expected", "note"}:
        return BugCommand(kind=command, text=text)
    if command in {"done", "exit", "quit"}:
        return BugCommand(kind="done")
    raise ValueError(f"Unsupported bug recording command: {tokens[0]}")


def generated_step_description(snapshot: SnapshotSummary) -> str:
    visible_texts = [value for value in snapshot.visible_texts if value.strip()]
    if visible_texts:
        return " / ".join(visible_texts[:2])
    visible_ids = [value for value in snapshot.visible_ids if value.strip()]
    if visible_ids:
        return " / ".join(visible_ids[:2])
    return "记录当前页面状态"


def build_capture(index: int, user_text: str | None, snapshot: SnapshotSummary) -> BugCapture:
    description = user_text or generated_step_description(snapshot)
    label = safe_name(description)
    return BugCapture(
        index=index,
        label=label,
        description=description,
        user_description=user_text,
        captured_at=datetime.now().isoformat(timespec="seconds"),
        snapshot=snapshot,
    )


def apply_review_command(recording: BugRecording, raw_command: str) -> BugRecording:
    normalized = raw_command.strip()
    if not normalized or normalized == "keep":
        return recording
    tokens = normalized.split(maxsplit=2)
    command = tokens[0].lower()
    if command == "rename" and len(tokens) == 3:
        target = int(tokens[1])
        updated = []
        for capture in recording.captures:
            if capture.index == target:
                updated.append(replace(capture, description=tokens[2], user_description=tokens[2], label=safe_name(tokens[2])))
            else:
                updated.append(capture)
        return replace(recording, captures=updated)
    if command == "delete" and len(tokens) == 2:
        target = int(tokens[1])
        remaining = [capture for capture in recording.captures if capture.index != target]
        reindexed = [replace(capture, index=index + 1) for index, capture in enumerate(remaining)]
        return replace(recording, captures=reindexed)
    raise ValueError("Usage: keep | rename <index> <text> | delete <index>")


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
        "notes": recording.notes,
        "steps": [asdict(capture) for capture in recording.captures],
    }


def _platform_label(platform: str) -> str:
    return "iOS" if platform.lower() == "ios" else "Android" if platform.lower() == "android" else platform


def _environment_lines(environment: dict[str, Any]) -> list[str]:
    lines = []
    for key, value in environment.items():
        if value is None or value == "":
            continue
        lines.append(f"- `{key}`: `{value}`")
    return lines


def render_bug_report(recording: BugRecording, recording_path: Path) -> str:
    step_lines = [f"{capture.index}. {capture.description}" for capture in recording.captures] or ["1. 未记录复现步骤"]
    evidence_lines = []
    previous_hash = None
    for capture in recording.captures:
        repeated = " (same page source as previous capture)" if previous_hash == capture.snapshot.source_hash else ""
        evidence_lines.append(f"- Step {capture.index}: {capture.description}{repeated}")
        if capture.snapshot.screenshot_path:
            evidence_lines.append(f"  - Screenshot: {capture.snapshot.screenshot_path}")
        if capture.snapshot.xml_path:
            evidence_lines.append(f"  - XML: {capture.snapshot.xml_path}")
        if capture.snapshot.capture_error:
            evidence_lines.append(f"  - Capture error: {capture.snapshot.capture_error}")
        previous_hash = capture.snapshot.source_hash
    notes = recording.notes or ["无"]
    return "\n".join(
        [
            f"# {recording.title}",
            "",
            "## Environment",
            f"- Platform: {_platform_label(recording.platform)}",
            *_environment_lines(recording.environment),
            "",
            "## Reproduction Steps",
            *step_lines,
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
    step_lines = [f"{capture.index}. {capture.description}" for capture in recording.captures] or ["1. 未记录复现步骤"]
    screenshot_lines = [
        f"- Step {capture.index}: {capture.snapshot.screenshot_path}"
        for capture in recording.captures
        if capture.snapshot.screenshot_path
    ]
    return "\n".join(
        [
            f"## 平台",
            _platform_label(recording.platform),
            "",
            "## 复现步骤",
            *step_lines,
            "",
            "## 期望结果",
            recording.expected_result or "未填写",
            "",
            "## 实际结果",
            recording.actual_result or "未填写",
            "",
            "## 证据截图",
            *(screenshot_lines or ["- 未生成截图"]),
            "",
            "## 本地报告",
            str(bug_report_path),
            "",
        ]
    )
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_bug_recording.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add apps/velowind-app/appium/velowind_appium/bug_recording.py apps/velowind-app/appium/tests/unit-test/test_bug_recording.py
git commit -m "feat: add appium bug recording core"
```

### Task 2: Shared Mobile Recorder CLI and Platform Metadata

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py`
- Modify: `apps/velowind-app/appium/velowind_appium/ios_manual_recording.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py`

- [ ] **Step 1: Write failing tests for platform config dispatch and metadata serialization**

Create `apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py`:

```python
from pathlib import Path

import pytest

from velowind_appium.mobile_manual_recording import (
    build_environment_metadata,
    default_recording_dir,
    resolve_platform_runtime,
)


def test_default_recording_dir_is_platform_specific():
    assert default_recording_dir("ios") == Path(".tmp/appium-ios/recordings")
    assert default_recording_dir("android") == Path(".tmp/appium-android/recordings")


def test_build_environment_metadata_for_ios():
    config = type(
        "IosConfig",
        (),
        {
            "server_url": "http://127.0.0.1:4723",
            "udid": "ios-udid",
            "device_name": "iPhone",
            "artifact_dir": Path(".tmp/appium-ios"),
            "bundle_id": "com.velowind.rider",
            "app_path": None,
            "platform_version": "26.2",
            "login_username": "13381509990",
        },
    )()

    metadata = build_environment_metadata("ios", config)

    assert metadata["platform"] == "ios"
    assert metadata["bundle_id"] == "com.velowind.rider"
    assert metadata["login_username_present"] is True
    assert "app_package" not in metadata


def test_build_environment_metadata_for_android():
    config = type(
        "AndroidConfig",
        (),
        {
            "server_url": "http://127.0.0.1:4724",
            "udid": "emulator-5554",
            "device_name": "Android Emulator",
            "artifact_dir": Path(".tmp/appium-android"),
            "target": "android_studio",
            "app_package": "com.velowind.rider",
            "app_activity": ".MainActivity",
            "app_path": "/tmp/app.apk",
            "platform_version": "15",
            "login_username": None,
        },
    )()

    metadata = build_environment_metadata("android", config)

    assert metadata["platform"] == "android"
    assert metadata["app_package"] == "com.velowind.rider"
    assert metadata["target"] == "android_studio"
    assert metadata["login_username_present"] is False
    assert "bundle_id" not in metadata


def test_resolve_platform_runtime_rejects_unknown_platform():
    with pytest.raises(ValueError, match="Unsupported platform"):
        resolve_platform_runtime("windows-phone")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement shared platform helpers and CLI skeleton**

Create `mobile_manual_recording.py` with the functions covered by tests and a CLI shell:

```python
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


@dataclass(frozen=True)
class PlatformRuntime:
    platform: str
    load_config: Callable[[], Any]
    create_driver: Callable[[Any], WebDriver]


def default_recording_dir(platform: str) -> Path:
    normalized = platform.strip().lower()
    if normalized == "ios":
        return Path(".tmp/appium-ios/recordings")
    if normalized == "android":
        return Path(".tmp/appium-android/recordings")
    raise ValueError(f"Unsupported platform: {platform}")


def resolve_platform_runtime(platform: str) -> PlatformRuntime:
    normalized = platform.strip().lower()
    if normalized == "ios":
        return PlatformRuntime("ios", load_ios_config, create_ios_driver)
    if normalized == "android":
        return PlatformRuntime("android", load_android_config, create_android_driver)
    raise ValueError(f"Unsupported platform: {platform}")


def _common_environment(platform: str, config: Any) -> dict[str, Any]:
    return {
        "platform": platform,
        "server_url": getattr(config, "server_url", None),
        "udid": getattr(config, "udid", None),
        "device_name": getattr(config, "device_name", None),
        "artifact_dir": str(getattr(config, "artifact_dir", "")),
        "platform_version": getattr(config, "platform_version", None),
        "login_username_present": bool(getattr(config, "login_username", None)),
    }


def build_environment_metadata(platform: str, config: Any) -> dict[str, Any]:
    normalized = platform.strip().lower()
    metadata = _common_environment(normalized, config)
    if normalized == "ios":
        metadata.update(
            {
                "bundle_id": getattr(config, "bundle_id", None),
                "app_path": getattr(config, "app_path", None),
            }
        )
        return {key: value for key, value in metadata.items() if value is not None}
    if normalized == "android":
        metadata.update(
            {
                "target": getattr(config, "target", None),
                "app_package": getattr(config, "app_package", None),
                "app_activity": getattr(config, "app_activity", None),
                "app_path": getattr(config, "app_path", None),
            }
        )
        return {key: value for key, value in metadata.items() if value is not None}
    raise ValueError(f"Unsupported platform: {platform}")


def build_parser(default_platform: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record mobile Appium journeys and bug evidence.")
    parser.add_argument("--platform", choices=["ios", "android"], default=default_platform)
    parser.add_argument("--mode", choices=["manual", "bug"], default="manual")
    parser.add_argument("--session-name")
    parser.add_argument("--test-name")
    parser.add_argument("--module-name")
    parser.add_argument("--output-dir")
    parser.add_argument("--taiga-project")
    return parser


def main(argv: list[str] | None = None, *, default_platform: str | None = None) -> int:
    parser = build_parser(default_platform)
    args = parser.parse_args(argv)
    platform = args.platform or default_platform
    if not platform:
        parser.error("--platform is required")
    runtime = resolve_platform_runtime(platform)
    if args.mode == "bug":
        from .bug_recording import parse_bug_command

        parse_bug_command("capture")
        print("Bug recording mode is available; capture loop is implemented in the next task.")
        return 0
    if runtime.platform == "ios":
        from .ios_manual_recording import record_ios_journey

        return record_ios_journey(args)
    parser.error("Manual action-command recording is currently supported only for iOS. Use --mode bug for Android.")
    return 2
```

Modify `ios_manual_recording.py` only at the bottom:

```python
def main(argv: list[str] | None = None) -> int:
    from .mobile_manual_recording import main as mobile_main

    return mobile_main(argv, default_platform="ios")
```

Keep the existing `record_ios_journey`, `parse_recording_command`, and generation helpers intact.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py apps/velowind-app/appium/velowind_appium/ios_manual_recording.py apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py
git commit -m "feat: add shared mobile recording cli"
```

### Task 3: Bug Capture Loop, Review Flow, and Artifact Writes

**Files:**
- Modify: `apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py`
- Modify: `apps/velowind-app/appium/velowind_appium/bug_recording.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py`

- [ ] **Step 1: Add tests for snapshot capture and report file writing using a fake driver**

Append to `test_mobile_manual_recording.py`:

```python
import json

from velowind_appium.mobile_manual_recording import capture_bug_snapshot, write_bug_recording_outputs


class FakeDriver:
    page_source = """
    <AppiumAUT>
      <node visible="true" content-desc="search-input" text="搜索" />
      <node visible="true" content-desc="loading-title" text="正在加载真实搜索结果" />
    </AppiumAUT>
    """

    def save_screenshot(self, path):
        Path(path).write_bytes(b"fake-png")


def test_capture_bug_snapshot_writes_screenshot_and_xml(tmp_path):
    snapshot = capture_bug_snapshot(FakeDriver(), tmp_path, "01-loading")

    assert snapshot.screenshot_path is not None
    assert snapshot.xml_path is not None
    assert "search-input" in snapshot.visible_ids
    assert "搜索" in snapshot.visible_texts
    assert snapshot.capture_error is None


def test_write_bug_recording_outputs_writes_json_report_and_taiga(tmp_path):
    from velowind_appium.bug_recording import BugCapture, BugRecording, SnapshotSummary

    recording = BugRecording(
        session_name="search-loading",
        platform="ios",
        title="搜索结果持续加载",
        environment={"platform": "ios", "bundle_id": "com.velowind.rider"},
        expected_result="应展示搜索结果",
        actual_result="页面一直加载中",
        notes=[],
        captures=[
            BugCapture(1, "loading", "页面持续加载", None, "2026-07-24T10:00:00", SnapshotSummary("/tmp/1.png", "/tmp/1.xml", "a", [], [], None)),
        ],
    )

    paths = write_bug_recording_outputs(recording, tmp_path)

    payload = json.loads(paths["recording"].read_text(encoding="utf-8"))
    assert payload["mode"] == "bug"
    assert paths["bug_report"].exists()
    assert paths["taiga_issue"].exists()
    assert "页面一直加载中" in paths["bug_report"].read_text(encoding="utf-8")
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py -q
```

Expected: FAIL because `capture_bug_snapshot` and `write_bug_recording_outputs` do not exist.

- [ ] **Step 3: Implement capture and output helpers**

Add to `mobile_manual_recording.py`:

```python
from datetime import datetime
from hashlib import sha1
import json

from selenium.common.exceptions import WebDriverException

from .actions import capture_debug_artifacts
from .artifacts import ensure_artifact_dir, safe_name
from .bug_recording import (
    BugRecording,
    SnapshotSummary,
    build_bug_recording_payload,
    render_bug_report,
    render_taiga_issue,
)
from .ios_manual_recording import extract_visible_identifiers


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
```

- [ ] **Step 4: Implement the interactive bug recording loop**

Add to `mobile_manual_recording.py`:

```python
from .bug_recording import BugCapture, build_capture, apply_review_command, parse_bug_command


def _prompt(message: str) -> str:
    import sys

    sys.stdout.write(message)
    sys.stdout.flush()
    return sys.stdin.readline().strip()


def _default_session_name(platform: str) -> str:
    return f"{platform}-bug-recording-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _review_recording(recording: BugRecording) -> BugRecording:
    current = recording
    while True:
        print("Captured steps:")
        for capture in current.captures:
            print(f"{capture.index}. {capture.description}")
        raw_command = _prompt("review> ").strip()
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
            captures=[capture for capture in captures if capture.index != 0],
        )
        reviewed = _review_recording(recording)
        paths = write_bug_recording_outputs(reviewed, artifact_dir)
        print(f"Bug report written: {paths['bug_report']}")
        print(f"Taiga issue draft written: {paths['taiga_issue']}")
        return 0
    finally:
        driver.quit()
```

Update `main` so `args.mode == "bug"` calls `record_bug_journey(args, runtime)`.

- [ ] **Step 5: Run focused tests and legacy tests**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_bug_recording.py apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py apps/velowind-app/appium/velowind_appium/bug_recording.py apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py
git commit -m "feat: record bug evidence and reports"
```

### Task 4: Package Scripts and Documentation

**Files:**
- Modify: `package.json`
- Modify: `apps/velowind-app/appium/README.md`
- Modify: `docs/ios-manual-recording.md`

- [x] **Step 1: Update package scripts**

Change scripts to:

```json
"appium:ios:record": "pnpm appium:ios:preflight && PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.mobile_manual_recording --platform ios",
"appium:android:record": "pnpm appium:android:preflight && PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.mobile_manual_recording --platform android",
"appium:ios:record:generate": "PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.generate_ios_test_from_recording"
```

Keep all other scripts unchanged.

- [x] **Step 2: Update docs with cross-platform bug-mode examples**

Add this section to `apps/velowind-app/appium/README.md` after the iOS recording commands:

```markdown
## Bug 录制

Bug 录制支持 iOS 真机和 Android 真机/模拟器。你在手机上正常操作 App，只在关键状态出现时在终端输入 `capture`。

```bash
pnpm appium:ios:record -- --mode bug --session-name search-loading
pnpm appium:android:record -- --mode bug --session-name search-loading
```

常用命令：

```text
capture
capture 打开搜索页
actual 页面一直加载中
expected 应展示搜索结果或错误态
note 偶发，第二次复跑通过
done
```

产物写入 `.tmp/appium-<platform>/recordings/<session-name>/`，其中 `bug-report.md` 用于人工确认，`taiga-issue.md` 可通过 Codex 的 Taiga MCP 创建 issue。当前 Taiga MCP 不支持附件上传，因此截图以本地路径形式写入 issue 描述。
```

Rename `docs/ios-manual-recording.md` to `docs/appium-manual-recording.md` if no external link depends on the old name. If keeping the old file, replace its title with `# Appium 手动录制与 Bug 录制` and add both iOS and Android bug examples.

- [x] **Step 3: Run JSON and focused unit validation**

Run:

```bash
node -e "JSON.parse(require('fs').readFileSync('package.json','utf8')); console.log('package.json ok')"
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py -q
```

Expected: `package.json ok` and pytest PASS.

- [x] **Step 4: Commit Task 4**

```bash
git add package.json apps/velowind-app/appium/README.md docs/ios-manual-recording.md docs/appium-manual-recording.md
git commit -m "docs: document cross-platform appium bug recording"
```

If `docs/appium-manual-recording.md` is not created, omit it from `git add`.

### Task 5: Report-First Script Generation Handoff

**Files:**
- Modify: `apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py`
- Modify: `apps/velowind-app/appium/velowind_appium/generate_ios_test_from_recording.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py`
- Test: `apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py`

- [ ] **Step 1: Add tests for iOS bug-mode generation from reviewed steps**

Append to `test_ios_manual_recording.py`:

```python
def test_generate_test_module_reads_bug_mode_steps(tmp_path):
    recording_path = tmp_path / "recording.json"
    recording_path.write_text(
        json.dumps(
            {
                "mode": "bug",
                "platform": "ios",
                "session_name": "search-loading",
                "module_name": "test_search_loading.py",
                "test_name": "test_search_loading",
                "steps": [
                    {
                        "index": 1,
                        "label": "open-search",
                        "description": "打开搜索页",
                        "snapshot": {"visible_ids": ["search-input"], "visible_texts": ["搜索"]},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rendered = render_test_module(json.loads(recording_path.read_text(encoding="utf-8")), recording_path)

    assert "test_search_loading" in rendered
    assert "wait_open_search" in rendered
    assert "search-input" in rendered
```

- [ ] **Step 2: Update generator to normalize legacy and bug-mode steps**

Add helper functions to `generate_ios_test_from_recording.py`:

```python
def normalized_recording_steps(recording: dict[str, Any]) -> list[dict[str, Any]]:
    if recording.get("mode") == "bug":
        steps = []
        for raw_step in recording.get("steps", []):
            steps.append(
                {
                    "label": raw_step.get("label") or raw_step.get("description") or f"step-{raw_step.get('index', len(steps) + 1)}",
                    "command": {"kind": "wait", "note": raw_step.get("description")},
                    "snapshot": raw_step.get("snapshot", {}),
                }
            )
        return steps
    return recording.get("steps", [])[1:]
```

Change `render_test_module` to:

```python
def render_test_module(recording: dict[str, Any], recording_path: Path) -> str:
    if recording.get("platform") not in {None, "ios"}:
        raise ValueError("iOS test generator only supports iOS recordings.")
    test_name = safe_name(recording.get("test_name") or f"test_{recording['session_name']}").replace("-", "_")
    blocks = [render_step_block(step) for step in normalized_recording_steps(recording)]
    body = "\n\n".join(blocks) if blocks else "    pass"
    return f"""import pytest

from velowind_appium.actions import (
    enter_text_if_present,
    safe_back,
    swipe_vertical,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    tap_text_if_present,
    wait_for_any_accessibility_id_or_text,
)
from velowind_appium.session import dismiss_common_system_alerts, ensure_logged_in_on_home


@pytest.mark.manual_recording
def {test_name}(driver, ios_config, step):
    \"\"\"Generated from manual recording: {recording_path}\"\"\"
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_logged_in_on_home(driver, ios_config))

{body}
"""
```

- [ ] **Step 3: Add post-report prompt that only runs iOS generation when confirmed**

In `record_bug_journey`, after output paths are printed, add:

```python
        if runtime.platform == "ios":
            answer = _prompt("是否基于这份 recording 生成 Appium pytest 脚本草稿？[y/N] ").strip().lower()
            if answer in {"y", "yes"}:
                from .generate_ios_test_from_recording import generate_test_module

                generated = generate_test_module(paths["recording"])
                print(f"Generated test draft: {generated}")
        else:
            print("Android bug report is complete. Android script generation will be added separately.")
```

Do not ask this question until `bug-report.md` and `taiga-issue.md` have already been written.

- [ ] **Step 4: Run generator and recording tests**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add apps/velowind-app/appium/velowind_appium/mobile_manual_recording.py apps/velowind-app/appium/velowind_appium/generate_ios_test_from_recording.py apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py
git commit -m "feat: hand off bug recordings to test generation"
```

### Task 6: End-to-End Verification

**Files:**
- No code files unless verification reveals a bug.

- [ ] **Step 1: Run the complete local unit test set for recording**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest \
  apps/velowind-app/appium/tests/unit-test/test_bug_recording.py \
  apps/velowind-app/appium/tests/unit-test/test_mobile_manual_recording.py \
  apps/velowind-app/appium/tests/unit-test/test_ios_manual_recording.py \
  apps/velowind-app/appium/tests/unit-test/test_android_config.py \
  apps/velowind-app/appium/tests/unit-test/test_config.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run CLI help checks**

Run:

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.mobile_manual_recording --help
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m velowind_appium.ios_manual_recording --help
```

Expected: both commands print usage and exit 0.

- [ ] **Step 3: Smoke the Android command without a device only enough to verify command wiring**

Run:

```bash
pnpm appium:android:record -- --help
```

Expected: usage output from `mobile_manual_recording`; it must not require a live Android device for `--help`.

- [ ] **Step 4: Manual iOS verification when a device is available**

Run:

```bash
pnpm appium:ios:record -- --mode bug --session-name recorder-smoke-ios
```

Use:

```text
capture 首页
expected 应保持首页可见
actual 首页可见
done
keep
n
```

Expected: `.tmp/appium-ios/recordings/recorder-smoke-ios/bug-report.md`, `recording.json`, and `taiga-issue.md` exist and include screenshot paths.

- [ ] **Step 5: Manual Android verification when a device or emulator is available**

Run:

```bash
pnpm appium:android:record -- --mode bug --session-name recorder-smoke-android
```

Use:

```text
capture 首页
expected 应保持首页可见
actual 首页可见
done
keep
```

Expected: `.tmp/appium-android/recordings/recorder-smoke-android/bug-report.md`, `recording.json`, and `taiga-issue.md` exist and include screenshot paths.

- [ ] **Step 6: Commit verification fixes only if needed**

If manual verification reveals a bug, fix only that bug, rerun the failing verification, and commit:

```bash
git add <changed-files>
git commit -m "fix: stabilize appium bug recording"
```

If no fixes are needed, do not create an empty commit.
