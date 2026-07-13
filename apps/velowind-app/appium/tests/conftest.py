import pytest
import os
from pathlib import Path
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver
from velowind_appium.reporting import allure, generate_and_open_allure_report
from velowind_appium.screenshots import capture_and_attach_debug_artifacts, capture_and_attach_page
from velowind_appium.session import ensure_logged_in_from_me_then_home


REPO_ROOT = Path(__file__).resolve().parents[4]
ALLURE_RESULTS = REPO_ROOT / ".tmp" / "appium-ios" / "allure-results"
ALLURE_REPORT = REPO_ROOT / ".tmp" / "appium-ios" / "allure-report"
WALKTHROUGH_TEST_FILE = "smoke/test_ios_feature_walkthrough.py"
_LOGGED_IN_SESSION_READY = False


def should_capture_each_step() -> bool:
    return os.environ.get("VW_APPIUM_CAPTURE_EACH_STEP", "").strip().lower() in {"1", "true", "yes", "y", "on"}


@pytest.fixture(scope="session")
def ios_config():
    config = load_ios_config()
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(scope="session")
def driver(ios_config):
    app_driver = create_ios_driver(ios_config)
    yield app_driver
    try:
        app_driver.quit()
    except (InvalidSessionIdException, WebDriverException):
        pass


def prepare_logged_in_session(driver, ios_config) -> bool:
    return ensure_logged_in_from_me_then_home(driver, ios_config)


@pytest.fixture(autouse=True)
def logged_in_session(request, ios_config):
    global _LOGGED_IN_SESSION_READY

    if _LOGGED_IN_SESSION_READY or "driver" not in request.fixturenames:
        return

    driver = request.getfixturevalue("driver")
    prepare_logged_in_session(driver, ios_config)
    _LOGGED_IN_SESSION_READY = True


@pytest.fixture
def capture_page(driver, ios_config, request):
    def _capture_page(label: str):
        return capture_and_attach_page(
            driver,
            ios_config.artifact_dir,
            label=f"{request.node.name}-{label}",
        )

    return _capture_page


@pytest.fixture
def step(capture_page):
    counter = {"value": 0}

    def _step(label: str, action=None, capture: bool = False):
        counter["value"] += 1
        step_label = f"{counter['value']:02d}-{label}"
        with allure.step(step_label):
            try:
                return action() if action is not None else None
            finally:
                if capture or should_capture_each_step():
                    capture_page(step_label)

    return _step


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call":
        return

    app_driver = item.funcargs.get("driver")
    ios_config = item.funcargs.get("ios_config")
    if app_driver is None or ios_config is None:
        return

    if report.passed:
        with allure.step("final-page"):
            capture_and_attach_page(app_driver, ios_config.artifact_dir, label=f"{item.name}-final-page")
        return

    if not report.passed:
        capture_and_attach_debug_artifacts(app_driver, ios_config.artifact_dir, label=item.name)


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("VW_APPIUM_AUTO_OPEN_REPORT") != "true":
        return
    if session.config.workerinput is not None if hasattr(session.config, "workerinput") else False:
        return
    if not any(item.location[0].endswith(WALKTHROUGH_TEST_FILE) for item in getattr(session, "items", [])):
        return

    generate_and_open_allure_report(
        repo_root=REPO_ROOT,
        allure_results=ALLURE_RESULTS,
        allure_report=ALLURE_REPORT,
    )
