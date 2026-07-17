import json
from pathlib import Path

from velowind_appium.generate_ios_test_from_recording import generate_test_module, render_test_module
from velowind_appium.ios_manual_recording import (
    build_recording_payload,
    extract_visible_identifiers,
    parse_recording_command,
    RecordingCommand,
    RecordingStep,
    SnapshotSummary,
)


def test_parse_recording_command_supports_tap_input_and_swipe():
    tap = parse_recording_command("tap bottom-nav-message 消息")
    assert tap == RecordingCommand(kind="tap", accessibility_id="bottom-nav-message", text="消息")

    input_command = parse_recording_command("input search-input 长白山骑行")
    assert input_command == RecordingCommand(kind="input", accessibility_id="search-input", value="长白山骑行")

    swipe = parse_recording_command("swipe up")
    assert swipe == RecordingCommand(kind="swipe", direction="up")


def test_extract_visible_identifiers_reads_useful_ids_and_texts():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeWindow visible="true" name="home-page-title" label="首页">
        <XCUIElementTypeButton visible="true" name="bottom-nav-message" label="消息" />
        <XCUIElementTypeStaticText visible="false" name="hidden-title" label="隐藏" />
      </XCUIElementTypeWindow>
    </AppiumAUT>
    """

    visible_ids, visible_texts = extract_visible_identifiers(page_source)

    assert visible_ids[:2] == ["home-page-title", "首页"]
    assert "bottom-nav-message" in visible_ids
    assert "消息" in visible_texts
    assert "隐藏" not in visible_texts


def test_generate_test_module_renders_recorded_actions(tmp_path):
    recording = {
        "session_name": "message-search",
        "module_name": "test_message_search.py",
        "test_name": "test_message_search",
        "steps": [
            {
                "index": 0,
                "label": "initial-state",
                "command": {"kind": "wait", "note": "initial-state"},
                "snapshot": {"visible_ids": ["home-page-title"], "visible_texts": ["首页"]},
            },
            {
                "index": 1,
                "label": "open-message-tab",
                "command": {
                    "kind": "tap",
                    "accessibility_id": "bottom-nav-message",
                    "text": "消息",
                },
                "snapshot": {"visible_ids": ["message-page-title"], "visible_texts": ["消息"]},
            },
        ],
    }

    rendered = render_test_module(recording, Path("/tmp/recording.json"))

    assert "tap_accessibility_id_or_text_if_present" in rendered
    assert "message-page-title" in rendered
    assert "manual_recording" in rendered


def test_build_recording_payload_and_write_generated_module(tmp_path):
    step = RecordingStep(
        index=1,
        label="open-message-tab",
        command=RecordingCommand(kind="tap", accessibility_id="bottom-nav-message", text="消息"),
        captured_at="2026-07-17T12:00:00",
        snapshot=SnapshotSummary(
            screenshot_path="/tmp/a.png",
            xml_path="/tmp/a.xml",
            source_hash="abc",
            visible_ids=["message-page-title"],
            visible_texts=["消息"],
        ),
    )
    config = type("Config", (), {"bundle_id": "com.velowind.rider", "udid": "device-001"})()
    payload = build_recording_payload(
        session_name="message-search",
        module_name="test_message_search.py",
        test_name="test_message_search",
        output_dir=tmp_path,
        steps=[step],
        config=config,
    )

    recording_path = tmp_path / "recording.json"
    recording_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    output_path = tmp_path / "test_message_search.py"

    generated = generate_test_module(recording_path, output_path)

    assert generated == output_path
    assert output_path.exists()
    assert "test_message_search" in output_path.read_text(encoding="utf-8")
