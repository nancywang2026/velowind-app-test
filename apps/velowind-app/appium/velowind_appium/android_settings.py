"""Temporary UiAutomator settings for flows with continuously updating video UI."""
from contextlib import contextmanager


@contextmanager
def android_idle_wait(driver, timeout_ms):
    if str((getattr(driver, 'capabilities', {}) or {}).get('platformName', '')).lower() != 'android':
        yield
        return
    previous = driver.get_settings()['waitForIdleTimeout']
    try:
        driver.update_settings({'waitForIdleTimeout': timeout_ms})
        yield
    finally:
        driver.update_settings({'waitForIdleTimeout': previous})


def without_android_idle_wait(driver):
    return android_idle_wait(driver, 0)
