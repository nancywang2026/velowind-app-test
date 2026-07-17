from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifacts import ensure_artifact_dir, safe_name


DEFAULT_MODULE_DIR = Path("apps/velowind-app/appium/tests/generated")


def load_recording(recording_path: Path) -> dict[str, Any]:
    return json.loads(recording_path.read_text(encoding="utf-8"))


def render_wait_assertion(step: dict[str, Any]) -> str:
    snapshot = step["snapshot"]
    visible_ids = snapshot.get("visible_ids") or []
    visible_texts = snapshot.get("visible_texts") or []
    ids_literal = repr(visible_ids[:5] or ["home-page-title"])
    texts_literal = repr(visible_texts[:5] or ["首页"])
    return (
        "wait_for_any_accessibility_id_or_text(\n"
        f"                driver,\n"
        f"                {ids_literal},\n"
        f"                {texts_literal},\n"
        "                timeout=20,\n"
        "            )"
    )


def render_action(step: dict[str, Any]) -> str | None:
    command = step["command"]
    kind = command["kind"]
    if kind == "tap":
        accessibility_id = command.get("accessibility_id")
        text = command.get("text")
        if text:
            return (
                "tap_accessibility_id_or_text_if_present(\n"
                f"                driver,\n"
                f"                {accessibility_id!r},\n"
                f"                {text!r},\n"
                "                timeout=8,\n"
                "            )"
            )
        return f"tap_if_present(driver, {accessibility_id!r}, timeout=8)"
    if kind == "tap_text":
        return f"tap_text_if_present(driver, {command['text']!r}, timeout=8)"
    if kind == "input":
        return (
            "enter_text_if_present(\n"
            f"                driver,\n"
            f"                {command['accessibility_id']!r},\n"
            f"                {command['value']!r},\n"
            "                timeout=8,\n"
            "            )"
        )
    if kind == "back":
        return "safe_back(driver)"
    if kind == "swipe":
        return f"swipe_vertical(driver, direction={command['direction']!r})"
    return None


def render_step_block(step: dict[str, Any]) -> str:
    label = safe_name(step["label"]).replace("-", "_")
    action = render_action(step)
    wait_assertion = render_wait_assertion(step)

    lines = []
    if action is not None:
        lines.append(
            f"    step(\n"
            f"        {label!r},\n"
            f"        lambda: {action},\n"
            f"        capture=True,\n"
            f"    )"
        )

    lines.append(
        f"    step(\n"
        f"        {f'wait_{label}'!r},\n"
        f"        lambda: {wait_assertion},\n"
        f"        capture=True,\n"
        f"    )"
    )
    return "\n".join(lines)


def render_test_module(recording: dict[str, Any], recording_path: Path) -> str:
    test_name = safe_name(recording["test_name"]).replace("-", "_")
    blocks = [render_step_block(step) for step in recording["steps"][1:]]
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


def generate_test_module(recording_path: Path, output_path: Path | None = None) -> Path:
    recording = load_recording(recording_path)
    target_dir = ensure_artifact_dir(output_path.parent if output_path else DEFAULT_MODULE_DIR)
    target_path = output_path or target_dir / recording["module_name"]
    target_path.write_text(render_test_module(recording, recording_path), encoding="utf-8")
    return target_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a pytest/Appium iOS test from a manual recording.")
    parser.add_argument("recording_path", help="Path to recording.json produced by ios_manual_recording.")
    parser.add_argument("--output", help="Explicit target test file path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = Path(args.output).expanduser() if args.output else None
    target_path = generate_test_module(Path(args.recording_path).expanduser(), output_path)
    print(f"Generated {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
