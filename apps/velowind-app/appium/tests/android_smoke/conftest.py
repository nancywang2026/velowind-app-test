import os
import time

import pytest
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

from velowind_appium.android_config import load_android_config
from velowind_appium.android_driver import create_android_driver
from velowind_appium.reporting import allure
from velowind_appium.screenshots import capture_and_attach_debug_artifacts, capture_and_attach_page
from .test_android_feature_walkthrough import prepare_android_home


def should_capture_each_step() -> bool:
    return os.environ.get("VW_APPIUM_CAPTURE_EACH_STEP", "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _progress(message: str) -> None:
    print(f"[appium-test] {message}", flush=True)


@pytest.fixture(scope="session")
def android_config():
    config = load_android_config()
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture(scope="session")
def android_driver(android_config):
    app_driver = create_android_driver(android_config)
    yield app_driver
    try:
        app_driver.quit()
    except (InvalidSessionIdException, WebDriverException):
        pass


@pytest.fixture(autouse=True)
def logged_in_session(android_driver, step):
    prepare_android_home(android_driver, step)
    yield


@pytest.fixture
def capture_page(android_driver, android_config, request):
    def _capture_page(label: str):
        return capture_and_attach_page(
            android_driver,
            android_config.artifact_dir,
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
    _progress(f"CASE START {nodeid}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        _progress(f"CASE {report.outcome.upper()} {item.nodeid}")
    if report.when != "call":
        return

    app_driver = item.funcargs.get("android_driver")
    android_config = item.funcargs.get("android_config")
    if app_driver is None or android_config is None:
        return

    if report.passed:
        with allure.step("final-page"):
            capture_and_attach_page(app_driver, android_config.artifact_dir, label=f"{item.name}-final-page")
        return

    capture_and_attach_debug_artifacts(app_driver, android_config.artifact_dir, label=item.name)
