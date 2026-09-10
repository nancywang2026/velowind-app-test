from contextlib import contextmanager


@contextmanager
def ios_media_idle_wait(driver):
    """Keep original quiescence checks during publishing and media validation."""
    if str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() != "ios":
        yield
        return
    # XCUITest settings can omit values supplied only as startup capabilities.
    capabilities = driver.capabilities
    initial = capabilities.get("waitForIdleTimeout", capabilities.get("appium:waitForIdleTimeout", 1.0))
    previous = driver.get_settings().get("waitForIdleTimeout", initial)
    required = max(1.0, previous)
    if required == previous:
        yield
        return
    driver.update_settings({"waitForIdleTimeout": required})
    try:
        yield
    finally:
        driver.update_settings({"waitForIdleTimeout": previous})
