from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from urllib.parse import urlsplit

import yaml


DEFAULT_CONFIG_FILE = Path(__file__).resolve().parents[1] / "cleanup.yaml"


@dataclass(frozen=True)
class CleanupConfig:
    note_matchers: list[str]
    activity_matchers: list[str]
    session_matchers: list[str]
    comment_matchers: list[str]
    delete_published_note_after_success: bool = False


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
        delete_published_note_after_success=_yaml_bool(
            cleanup.get("delete_published_note_after_success"),
            default=False,
        ),
    )


def matches_test_data(text: str, matchers: list[str]) -> bool:
    if not text:
        return False
    return any(matcher in text for matcher in matchers)


def note_cleanup_mode() -> str:
    raw = os.environ.get("VW_NOTE_CLEANUP_MODE")
    if raw is None:
        cleanup = _read_yaml_config().get("cleanup", {})
        raw = cleanup.get("note_cleanup_mode", "ui") if isinstance(cleanup, dict) else "ui"
    mode = str(raw).strip().lower()
    if mode not in {"ui", "api"}:
        raise ValueError("note_cleanup_mode / VW_NOTE_CLEANUP_MODE must be ui or api")
    return mode


def note_cleanup_api_base_url() -> str:
    raw = os.environ.get("VW_NOTE_CLEANUP_API_BASE_URL")
    if raw is None:
        cleanup = _read_yaml_config().get("cleanup", {})
        cleanup = cleanup if isinstance(cleanup, dict) else {}
        raw = cleanup.get("note_cleanup_api_base_url")
        if raw is None:
            environment = str(os.environ.get("VW_API_ENV", "uat")).strip().lower()
            hosts = {
                "uat": ("VW_UAT_API_HOST", "https://uat-api.velowind.com"),
                "prod": ("VW_PROD_API_HOST", "https://prod-api.velowind.com"),
            }
            if environment not in hosts:
                raise ValueError("api_environment / VW_API_ENV must be uat or prod")
            variable, default_host = hosts[environment]
            raw = os.environ.get(variable, default_host)
    base = str(raw or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/api/v1/mobile")):
        raise ValueError("Configure a valid HTTPS note_cleanup_api_base_url / VW_NOTE_CLEANUP_API_BASE_URL matching the app environment")
    return base if parsed.path else base + "/api/v1/mobile"


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


def _yaml_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
