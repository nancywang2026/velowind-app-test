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
    options = AppiumOptions()
    options.load_capabilities(build_android_capabilities(config))
    driver = webdriver.Remote(command_executor=config.server_url, options=options)
    install_android_script_compatibility(driver)
    driver.implicitly_wait(0)
    return driver
