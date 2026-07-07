from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.webdriver import WebDriver

from .config import IosAppiumConfig, build_ios_capabilities


def create_ios_driver(config: IosAppiumConfig) -> WebDriver:
    options = AppiumOptions()
    options.load_capabilities(build_ios_capabilities(config))
    driver = webdriver.Remote(command_executor=config.server_url, options=options)
    driver.implicitly_wait(0)
    return driver
