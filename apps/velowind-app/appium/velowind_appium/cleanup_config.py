from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_FILE = Path(__file__).resolve().parents[1] / "cleanup.yaml"


@dataclass(frozen=True)
class CleanupConfig:
    note_matchers: list[str]
    activity_matchers: list[str]
    session_matchers: list[str]
    comment_matchers: list[str]


def load_cleanup_config() -> CleanupConfig:
    data = _read_yaml_config()
    cleanup = data.get("cleanup") if isinstance(data, dict) else {}
    if not isinstance(cleanup, dict):
        cleanup = {}

    return CleanupConfig(
        note_matchers=_yaml_string_list(cleanup.get("note_matchers")),
        activity_matchers=_yaml_string_list(cleanup.get("activity_matchers")),
        session_matchers=_yaml_string_list(cleanup.get("session_matchers")),
        comment_matchers=_yaml_string_list(cleanup.get("comment_matchers")),
    )


def matches_test_data(text: str, matchers: list[str]) -> bool:
    if not text:
        return False
    return any(matcher in text for matcher in matchers)


def _read_yaml_config() -> dict[str, Any]:
    config_path = Path(os.environ.get("VW_APPIUM_CLEANUP_CONFIG_FILE", str(DEFAULT_CONFIG_FILE))).expanduser()
    if not config_path.exists():
        return {}
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _yaml_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
