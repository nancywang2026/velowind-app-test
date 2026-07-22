import pytest
import os
import time
from pathlib import Path
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

from velowind_appium.android_config import load_android_config
from velowind_appium.android_driver import create_android_driver
from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver
from velowind_appium.reporting import allure, generate_and_open_allure_report
from velowind_appium.screenshots import capture_and_attach_debug_artifacts, capture_and_attach_page
from velowind_appium.session import ensure_logged_in_on_home


REPO_ROOT = Path(__file__).resolve().parents[4]
ALLURE_RESULTS = REPO_ROOT / ".tmp" / "appium-ios" / "allure-results"
ALLURE_REPORT = REPO_ROOT / ".tmp" / "appium-ios" / "allure-report"
WALKTHROUGH_TEST_FILE = "smoke/test_ios_feature_walkthrough.py"


def should_capture_each_step() -> bool:
    return os.environ.get("VW_APPIUM_CAPTURE_EACH_STEP", "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _progress(message: str) -> None:
    print(f"[appium-test] {message}", flush=True)


def _is_android_smoke_nodeid(nodeid: str) -> bool:
    return "/android_smoke/" in nodeid or "::android_smoke/" in nodeid


def _should_log_progress(nodeid: str) -> bool:
    return "/unit-test/" not in nodeid and not _is_android_smoke_nodeid(nodeid)


@pytest.fixture(scope="session")
def ios_config():
    config = load_test_config()
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    return config


def _test_platform() -> str:
    return os.environ.get("VW_APPIUM_PLATFORM", "ios").strip().lower()


def load_test_config():
    if _test_platform() == "android":
        return load_android_config()
    return load_ios_config()


def create_test_driver(config):
    if _test_platform() == "android":
        return create_android_driver(config)
    return create_ios_driver(config)


@pytest.fixture(scope="session")
def driver(ios_config):
    app_driver = create_test_driver(ios_config)
    yield app_driver
    try:
        app_driver.quit()
    except (InvalidSessionIdException, WebDriverException):
        pass


def prepare_logged_in_session(driver, ios_config) -> bool:
    return ensure_logged_in_on_home(driver, ios_config)


@pytest.fixture(autouse=True)
def logged_in_session(request, ios_config):
    if "driver" not in request.fixturenames:
        yield
        return
    request_node = getattr(request, "node", None)
    if request_node is not None and request_node.get_closest_marker("skip_home_session") is not None:
        yield
        return

    driver = request.getfixturevalue("driver")
    prepare_logged_in_session(driver, ios_config)
    try:
        yield
    finally:
        prepare_logged_in_session(driver, ios_config)


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
        started_at = time.monotonic()
        _progress(f"STEP START {step_label}")
        with allure.step(step_label):
            try:
                result = action() if action is not None else None
                _progress(f"STEP PASS  {step_label} ({time.monotonic() - started_at:.1f}s)")
                return result
            except Exception as exc:
                _progress(
                    f"STEP FAIL  {step_label} ({time.monotonic() - started_at:.1f}s): "
                    f"{type(exc).__name__}: {exc}"
                )
                raise
            finally:
                if capture or should_capture_each_step():
                    capture_page(step_label)

    return _step


def pytest_runtest_logstart(nodeid, location):
    if not _should_log_progress(nodeid):
        return
    _progress(f"CASE START {nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    nodeid = getattr(item, "nodeid", "")
    if nodeid and not _should_log_progress(nodeid):
        return
    if report.when == "call":
        outcome = getattr(report, "outcome", None)
        if outcome is None:
            outcome = "passed" if getattr(report, "passed", False) else "failed"
        _progress(f"CASE {str(outcome).upper()} {nodeid or getattr(item, 'name', '<unknown>')}")
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
