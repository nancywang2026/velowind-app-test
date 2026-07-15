from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.webdriver import WebDriver

from .android_config import AndroidAppiumConfig, build_android_capabilities


def create_android_driver(config: AndroidAppiumConfig) -> WebDriver:
    options = AppiumOptions()
    options.load_capabilities(build_android_capabilities(config))
    driver = webdriver.Remote(command_executor=config.server_url, options=options)
    driver.implicitly_wait(0)
    return driver
