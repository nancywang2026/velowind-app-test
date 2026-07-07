import allure
import pytest
import shutil
import subprocess
from pathlib import Path

from velowind_appium.actions import capture_debug_artifacts, capture_page_screenshot
from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver


REPO_ROOT = Path(__file__).resolve().parents[4]
ALLURE_RESULTS = REPO_ROOT / ".tmp" / "appium-ios" / "allure-results"
ALLURE_REPORT = REPO_ROOT / ".tmp" / "appium-ios" / "allure-report"
WALKTHROUGH_TEST_FILE = "test_ios_feature_walkthrough.py"


@pytest.fixture(scope="session")
def ios_config():
    config = load_ios_config()
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(scope="session")
def driver(ios_config):
    app_driver = create_ios_driver(ios_config)
    yield app_driver
    app_driver.quit()


@pytest.fixture
def capture_page(driver, ios_config, request):
    def _capture_page(label: str):
        screenshot = capture_page_screenshot(driver, ios_config.artifact_dir, f"{request.node.name}-{label}")
        if screenshot is not None:
            allure.attach.file(str(screenshot), name=screenshot.name, attachment_type=allure.attachment_type.PNG)
        return screenshot

    return _capture_page


@pytest.fixture
def step(capture_page):
    counter = {"value": 0}

    def _step(label: str, action=None):
        counter["value"] += 1
        step_label = f"{counter['value']:02d}-{label}"
        with allure.step(step_label):
            try:
                return action() if action is not None else None
            finally:
                capture_page(step_label)

    return _step


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.passed:
        return

    app_driver = item.funcargs.get("driver")
    ios_config = item.funcargs.get("ios_config")
    if app_driver is not None and ios_config is not None:
        artifacts = capture_debug_artifacts(app_driver, ios_config.artifact_dir, item.name)
        attachment_types = {
            "PNG": allure.attachment_type.PNG,
            "XML": allure.attachment_type.XML,
        }
        for label, path in artifacts.items():
            allure.attach.file(str(path), name=path.name, attachment_type=attachment_types[label])


def pytest_sessionfinish(session, exitstatus):
    if session.config.workerinput is not None if hasattr(session.config, "workerinput") else False:
        return
    if not any(item.location[0].endswith(WALKTHROUGH_TEST_FILE) for item in getattr(session, "items", [])):
        return

    allure_bin = shutil.which("allure")
    if allure_bin is None or not ALLURE_RESULTS.exists():
        return

    generate_result = subprocess.run(
        [
            allure_bin,
            "generate",
            str(ALLURE_RESULTS),
            "--clean",
            "-o",
            str(ALLURE_REPORT),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if generate_result.returncode != 0:
        return

    subprocess.Popen([allure_bin, "open", str(ALLURE_REPORT)], cwd=REPO_ROOT)
