"""External data only: JSON config + optional Postman environment variables."""
import json
import math
import os
import re
from pathlib import Path
from .http import validate_url


class ConfigError(ValueError):
    pass


def load_config(path, environment=None, environ=None):
    variables = {}
    try:
        if environment:
            source = json.loads(Path(environment).read_text())
            variables.update({v["key"]: v.get("value", "") for v in source["values"]
                              if v.get("enabled", True)})
        # OS environment takes precedence without writing secrets back to disk.
        variables.update(os.environ if environ is None else environ)
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError, KeyError, TypeError):
        raise ConfigError("Cannot parse data/environment JSON file") from None

    def resolve(value):
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if isinstance(value, str):
            def substitute(match):
                name = match.group(1)
                result = variables.get(name)
                if result is None or not str(result).strip() or '{{' in str(result) or '${' in str(result):
                    raise ConfigError(f"Missing/unresolved variable: {name}")
                return str(result)
            return re.sub(r"\$\{([a-zA-Z_][a-zA-Z_0-9]*)\}", substitute, value)
        return value

    data = resolve(raw)
    validate_config(data)
    return data


def validate_config(data):
    def text(value, label):
        if (not isinstance(value, str) or not value.strip() or '{{' in value or '${' in value
                or set(value) <= {"*", "•", "●"}):
            raise ConfigError(f"Missing/unresolved text: {label}")

    def number(value, label, minimum, integer=False):
        if (type(value) not in ((int,) if integer else (int, float))
                or not math.isfinite(value) or value < minimum):
            raise ConfigError(f"Invalid numeric setting: {label}")

    try:
        text(data["base_url"], "base_url")
        validate_url(data["base_url"])
        phones = []
        for role in ("a", "b", "c"):
            account = data["accounts"][role]
            for field in ("phone", "password"):
                text(account[field], f"accounts.{role}.{field}")
            phones.append(account["phone"])
        if len(set(phones)) != 3:
            raise ConfigError("A/B/C must use three different accounts")
        for field in ("post_id", "activity_id"):
            text(data["resources"][field], field)
        for recipient in ("to_b", "to_c"):
            batch = data["messages"][recipient]
            number(batch["count"], recipient + ".count", 1, True)
            text(batch["template"], recipient + ".template")
            batch["template"].format(run_id="check", index=1, count=batch["count"])
        for kind in ("post_share", "activity_share"):
            text(data["messages"][kind], kind)
            data["messages"][kind].format(run_id="check")
        expected = data["expected"]
        for key in ("baseline_unread_b", "unread_b", "unread_delta_b"):
            number(expected[key], key, 0, True)
        if (expected["unread_delta_b"] != data["messages"]["to_b"]["count"]
                or expected["unread_b"] != expected["baseline_unread_b"] + expected["unread_delta_b"]):
            raise ConfigError("Unread expectations must match baseline + to_b.count")
        preparation = data.get("preparation", {})
        if not isinstance(preparation, dict) or type(preparation.get("mark_b_history_read", False)) is not bool:
            raise ConfigError("preparation.mark_b_history_read must be boolean")
        if preparation.get("mark_b_history_read") and expected["baseline_unread_b"] != 0:
            raise ConfigError("mark_b_history_read requires baseline_unread_b=0")
        execution = data["execution"]
        number(execution["http_timeout_seconds"], "http_timeout_seconds", 0.01)
        number(execution["request_interval_seconds"], "request_interval_seconds", 0)
        number(execution.get("send_interval_seconds", 0), "send_interval_seconds", 0)
        number(execution["page_size"], "page_size", 1, True)
        number(execution["max_pages"], "max_pages", 1, True)
        if execution["page_size"] > 50:
            raise ConfigError("page_size must be <= 50")
        # The initial API returns the newest page, not a backwards cursor.
        if execution["page_size"] < max(data["messages"][x]["count"] for x in ("to_b", "to_c")) + 1:
            raise ConfigError("page_size must include the text batch plus its share message")
    except ConfigError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise ConfigError("Invalid config schema, URL or message format fields") from None
