from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from .config import IosAppiumConfig, build_ios_capabilities
from .preflight import format_wda_startup_error, is_wda_startup_error, write_wda_startup_diagnostic


def create_ios_driver(config: IosAppiumConfig) -> WebDriver:
    options = AppiumOptions()
    options.load_capabilities(build_ios_capabilities(config))
    try:
        driver = webdriver.Remote(command_executor=config.server_url, options=options)
    except WebDriverException as error:
        if config.target == "device" and is_wda_startup_error(str(error)):
            diagnostic_path = write_wda_startup_diagnostic(config, error)
            raise RuntimeError(format_wda_startup_error(config, error, diagnostic_path)) from error
        raise
    driver.implicitly_wait(0)
    return driver
