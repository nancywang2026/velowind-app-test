import allure
import pytest

from velowind_appium.actions import capture_debug_artifacts, capture_page_screenshot
from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver


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
            result = action() if action is not None else None
            capture_page(step_label)
            return result

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
