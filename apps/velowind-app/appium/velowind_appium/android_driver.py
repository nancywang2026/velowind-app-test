import os

from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.webdriver import WebDriver

from .android_config import AndroidAppiumConfig, build_android_capabilities


def install_android_script_compatibility(driver: WebDriver) -> WebDriver:
    original_execute_script = driver.execute_script

    def execute_script(script: str, payload=None):
        if script == "mobile: tap":
            return original_execute_script("mobile: clickGesture", payload or {})
        if script == "mobile: swipe" and isinstance(payload, dict) and payload.get("direction"):
            rect = driver.get_window_rect()
            return original_execute_script(
                "mobile: swipeGesture",
                {
                    "left": int(rect["width"] * 0.10),
                    "top": int(rect["height"] * 0.20),
                    "width": int(rect["width"] * 0.80),
                    "height": int(rect["height"] * 0.60),
                    "direction": payload["direction"],
                    "percent": 0.75,
                },
            )
        return original_execute_script(script, payload) if payload is not None else original_execute_script(script)

    driver.execute_script = execute_script
    return driver


def create_android_driver(config: AndroidAppiumConfig) -> WebDriver:
    idle_timeout = int(os.environ.get("VW_ANDROID_WAIT_FOR_IDLE_TIMEOUT_MS", "1000"))
    if idle_timeout < 0:
        raise ValueError("VW_ANDROID_WAIT_FOR_IDLE_TIMEOUT_MS must be non-negative")
    options = AppiumOptions()
    options.load_capabilities(build_android_capabilities(config))
    driver = webdriver.Remote(command_executor=config.server_url, options=options)
    try:
        # Video and RN animations can keep the accessibility stream busy.
        # Bound the native idle wait; existing explicit UI waits still decide
        # when the target control/page is ready, with no assertion changes.
        driver.update_settings({"waitForIdleTimeout": idle_timeout})
        install_android_script_compatibility(driver)
        driver.implicitly_wait(0)
    except Exception:
        driver.quit()
        raise
    return driver
