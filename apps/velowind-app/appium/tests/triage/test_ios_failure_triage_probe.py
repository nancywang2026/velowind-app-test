"""Explicit live integration probe; intentional failure must never become a product bug."""
import os

import pytest
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait


pytestmark = [
    pytest.mark.skip_home_session,
    pytest.mark.skipif(os.environ.get('VW_APPIUM_TRIAGE_LIVE_PROBE') != 'true',
                       reason='Explicit live triage validation only'),
]


def test_live_appium_connection_is_readable(driver, ios_config, step):
    def check():
        rect = driver.get_window_rect()
        assert rect['width'] > 0 and rect['height'] > 0
        assert driver.query_app_state(ios_config.bundle_id) == 4
        assert driver.current_context == 'NATIVE_APP'
        WebDriverWait(driver, 30).until(lambda d: any(e.is_displayed() for e in d.find_elements(AppiumBy.ACCESSIBILITY_ID, 'bottom-nav-activity')))
    step('read-only-device-and-foreground-app', check, capture=True)


def test_intentional_failure_captures_device_evidence(driver, ios_config, step):
    def probe():
        assert driver.query_app_state(ios_config.bundle_id) == 4
        pytest.fail('INTENTIONAL_TRIAGE_PROBE: planned framework validation, not a product defect; do not create a Bug or weaken/remove this probe')
    step('intentional-triage-failure-for-evidence-only', probe)
