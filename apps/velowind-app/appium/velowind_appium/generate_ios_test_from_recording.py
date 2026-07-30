from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifacts import ensure_artifact_dir, safe_name


DEFAULT_MODULE_DIR = Path("apps/velowind-app/appium/tests/generated")


def load_recording(recording_path: Path) -> dict[str, Any]:
    return json.loads(recording_path.read_text(encoding="utf-8"))


def default_module_name(recording: dict[str, Any]) -> str:
    session_name = recording.get("session_name") or recording.get("title") or "recording"
    stem = safe_name(f"test_{session_name}").replace("-", "_")
    return f"{stem}.py"


def infer_bug_command(raw_step: dict[str, Any]) -> dict[str, Any]:
    description = str(raw_step.get("description") or raw_step.get("user_description") or "")
    if "点击租车" in description:
        return {
            "kind": "python",
            "code": (
                "(\n"
                "                open_rental_from_home(driver, timeout=25),\n"
                "                choose_first_store(driver, timeout=15),\n"
                "                tap_select_car_now(driver, timeout=20),\n"
                "            )"
            ),
        }
    if "立即预订" in description or "立即预定" in description:
        return {
            "kind": "python",
            "code": (
                "(\n"
                "                open_available_vehicle_detail(driver, timeout=20),\n"
                "                tap_book_now(driver, timeout=20),\n"
                "            )"
            ),
        }
    if "提交订单" in description:
        return {"kind": "python", "code": "submit_rental_order(driver, timeout=25)"}
    if "去支付" in description:
        return {"kind": "python", "code": "tap_rental_payment_button(driver, timeout=20)", "skip_wait": True}
    return {"kind": "wait", "note": description}


def actual_result_text(recording: dict[str, Any]) -> str | None:
    actual = str(recording.get("actual_result") or "").strip()
    if not actual:
        return None
    if "“" in actual and "”" in actual:
        return actual.split("“", 1)[1].split("”", 1)[0].strip()
    return actual.removeprefix("页面显示").strip(" ：:")


def bug_step_label(recording: dict[str, Any], raw_step: dict[str, Any], fallback_index: int) -> str:
    label = raw_step.get("label")
    description = raw_step.get("description") or raw_step.get("user_description")
    if label and label != recording.get("session_name"):
        return label
    return description or label or f"step-{raw_step.get('index', fallback_index)}"


def normalized_recording_steps(recording: dict[str, Any]) -> list[dict[str, Any]]:
    if recording.get("mode") == "bug":
        steps = []
        for raw_step in recording.get("steps", []):
            steps.append(
                {
                    "label": bug_step_label(recording, raw_step, len(steps) + 1),
                    "command": infer_bug_command(raw_step),
                    "snapshot": raw_step.get("snapshot", {}),
                }
            )
        actual_text = actual_result_text(recording)
        if actual_text:
            steps.append(
                {
                    "label": "点击确认并回退回App",
                    "command": {
                        "kind": "python",
                        "code": (
                            "(\n"
                            "                tap_text_if_present(driver, '确认', timeout=8),\n"
                            "                safe_back(driver),\n"
                            "                driver.activate_app(ios_config.bundle_id),\n"
                            "            )"
                        ),
                    },
                    "snapshot": {},
                }
            )
            steps.append(
                {
                    "label": "验证实际错误提示",
                    "command": {"kind": "wait", "note": actual_text},
                    "snapshot": {"visible_ids": [actual_text], "visible_texts": [actual_text]},
                }
            )
        return steps
    return recording.get("steps", [])[1:]


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
    if kind == "python":
        return command["code"]
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

    if not step["command"].get("skip_wait"):
        lines.append(
            f"    step(\n"
            f"        {f'wait_{label}'!r},\n"
            f"        lambda: {wait_assertion},\n"
            f"        capture=True,\n"
            f"    )"
        )
    return "\n".join(lines)


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
from velowind_appium.modules import (
    choose_first_store,
    open_available_vehicle_detail,
    open_rental_from_home,
    submit_rental_order,
    tap_book_now,
    tap_rental_payment_button,
    tap_select_car_now,
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
    target_path = output_path or target_dir / (recording.get("module_name") or default_module_name(recording))
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
