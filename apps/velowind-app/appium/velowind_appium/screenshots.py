from __future__ import annotations

from pathlib import Path
from typing import Dict

from appium.webdriver.webdriver import WebDriver

from velowind_appium.actions import capture_debug_artifacts, capture_page_screenshot
from velowind_appium.reporting import allure, attach_file_if_present


def capture_and_attach_page(
    driver: WebDriver,
    artifact_dir: Path,
    *,
    label: str,
) -> Path | None:
    screenshot = capture_page_screenshot(driver, artifact_dir, label)
    attach_file_if_present(
        screenshot,
        name=screenshot.name if screenshot is not None else None,
        attachment_type=allure.attachment_type.PNG,
    )
    return screenshot


def capture_and_attach_debug_artifacts(
    driver: WebDriver,
    artifact_dir: Path,
    *,
    label: str,
) -> Dict[str, Path]:
    artifacts = capture_debug_artifacts(driver, artifact_dir, label)
    attachment_types = {
        "PNG": allure.attachment_type.PNG,
        "XML": allure.attachment_type.XML,
    }
    for artifact_type, path in artifacts.items():
        attach_file_if_present(path, name=path.name, attachment_type=attachment_types[artifact_type])
    return artifacts
