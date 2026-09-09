from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from string import Formatter
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).resolve().parents[2] / "tests/message_system/config"
TOKEN = re.compile(r"\$\{([a-zA-Z0-9_.]+)\}")


class ConfigurationError(ValueError):
    """A configuration cannot be used without silently guessing its meaning."""


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ConfigurationError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(path: Path) -> dict:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load YAML: {path.name}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"Expected YAML mapping: {path.name}")
    return value


def resolve(value: Any, context: dict) -> Any:
    """Resolve whitelisted dotted lookups, never eval; preserve scalar types."""
    def lookup(match):
        current = context
        for part in match.group(1).split("."):
            if not isinstance(current, dict) or part not in current:
                raise ConfigurationError(f"Unresolved reference: {match.group(1)}")
            current = current[part]
        if current is None or isinstance(current, (dict, list)):
            raise ConfigurationError(f"Reference must resolve to a scalar: {match.group(1)}")
        return current

    if isinstance(value, str):
        match = TOKEN.fullmatch(value)
        result = lookup(match) if match else TOKEN.sub(lambda m: str(lookup(m)), value)
        if isinstance(result, str) and "${" in result:
            raise ConfigurationError("Malformed or recursive placeholder")
        return result
    if isinstance(value, list):
        return [resolve(v, context) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, context) for k, v in value.items()}
    return value


class TestData:
    __test__ = False

    def __init__(self, path: Path | None = None):
        self.raw = load_yaml(path or Path(os.getenv("VW_MESSAGE_DATA_FILE", CONFIG_DIR / "test_data.yaml")))
        if self.raw.get("schema_version") != 1:
            raise ConfigurationError("Unsupported test data schema")
        for name in ("execution", "accounts", "rules", "scenarios"):
            if not isinstance(self.raw.get(name), dict):
                raise ConfigurationError(f"Missing mapping: {name}")
        for name in ("page_timeout_seconds", "business_timeout_seconds", "poll_seconds", "http_timeout_seconds", "hold_seconds"):
            value = self.raw["execution"].get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ConfigurationError(f"Invalid positive timeout: {name}")
        scrolls = self.execution.get("max_scrolls")
        if type(scrolls) is not int or scrolls <= 0:
            raise ConfigurationError("max_scrolls must be a positive integer")
        if set(self.raw["scenarios"]) != {f"MSG-A{i:02}" for i in range(1, 9)}:
            raise ConfigurationError("Expected eight message scenarios")
        for case_id, case in self.raw["scenarios"].items():
            if not isinstance(case.get("setup"), dict) or not isinstance(case.get("expected"), dict):
                raise ConfigurationError(f"Missing setup/expected: {case_id}")
            if case.get("actor") not in self.raw["accounts"]:
                raise ConfigurationError(f"Unknown actor: {case_id}")
        if self.raw["rules"].get("notification_read_mode") != "per_item_click":
            raise ConfigurationError("Notification rule differs from the approved per-item rule")
        if self.raw["rules"].get("hidden_chat_on_new_message") != "stay_hidden":
            raise ConfigurationError("Hidden-chat rule differs from the approved stay-hidden rule")

    @property
    def execution(self):
        return self.raw["execution"]

    def case(self, case_id: str) -> dict:
        if case_id not in self.raw["scenarios"]:
            raise ConfigurationError(f"Unknown scenario: {case_id}")
        return copy.deepcopy(self.raw["scenarios"][case_id])

    def credentials(self, role: str) -> tuple[str, str]:
        account = self.raw["accounts"][role]
        result = []
        for field in ("username_env", "password_env"):
            name = account[field]
            if not os.getenv(name):
                raise ConfigurationError(f"Missing environment variable: {name}")
            result.append(os.environ[name])
        return tuple(result)


class Locators:
    def __init__(self, path: Path | None = None):
        self.raw = load_yaml(path or Path(os.getenv("VW_MESSAGE_LOCATORS_FILE", CONFIG_DIR / "accessibility_ids.yaml")))
        if self.raw.get("schema_version") != 1 or self.raw.get("strategy") != "accessibility_id":
            raise ConfigurationError("Only accessibility_id locators are permitted")
        self.ids = self.raw.get("ids", {})
        if not self.ids or any(not isinstance(v, str) or not v for v in self.ids.values()):
            raise ConfigurationError("Locator IDs must be non-empty strings")
        for template in self.ids.values():
            for _, field, spec, conversion in Formatter().parse(template):
                if field is not None and (not field.isidentifier() or spec or conversion):
                    raise ConfigurationError("Only simple named locator parameters are permitted")

    def get(self, key: str, **parameters) -> str:
        if key not in self.ids:
            raise ConfigurationError(f"Unknown accessibility ID key: {key}")
        required = {field for _, field, _, _ in Formatter().parse(self.ids[key]) if field is not None}
        if set(parameters) != required or any(v is None or str(v) == "" for v in parameters.values()):
            raise ConfigurationError(f"Invalid parameters for accessibility ID: {key}")
        return self.ids[key].format(**parameters)
