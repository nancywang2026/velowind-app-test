from __future__ import annotations

from pathlib import Path


def platform_display_name(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized == "android":
        return "Android"
    if normalized == "ios":
        return "iOS"
    return platform.strip() or "unknown"


def device_kind(platform: str, target: str | None, udid: str | None = None) -> str:
    normalized_platform = platform.strip().lower()
    normalized_target = (target or "").strip().lower()
    normalized_udid = (udid or "").strip().lower()

    if normalized_platform == "ios":
        return "virtual" if normalized_target in {"simulator", "sim"} else "physical"
    if normalized_platform == "android":
        if normalized_target == "physical":
            return "physical"
        if normalized_udid and not normalized_udid.startswith("emulator-") and ":" not in normalized_udid:
            return "physical"
        return "virtual"
    return "unknown"


def build_allure_environment(platform: str, config) -> dict[str, str]:
    target = str(getattr(config, "target", "") or "")
    udid = str(getattr(config, "udid", "") or "")
    environment = {
        "Platform": platform_display_name(platform),
        "Device Kind": device_kind(platform, target, udid),
        "Target": target or "unknown",
    }

    device_name = getattr(config, "device_name", None)
    if device_name:
        environment["Device Name"] = str(device_name)
    if udid:
        environment["UDID"] = udid

    platform_version = getattr(config, "platform_version", None)
    if platform_version:
        environment["Platform Version"] = str(platform_version)

    server_url = getattr(config, "server_url", None)
    if server_url:
        environment["Appium Server"] = str(server_url)

    return environment


def write_allure_environment(results_dir: Path, environment: dict[str, str]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / "environment.properties"
    lines = [f"{_escape_property(key)}={_escape_property(value)}" for key, value in sorted(environment.items())]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _escape_property(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("=", "\\=")
        .replace(":", "\\:")
    )
