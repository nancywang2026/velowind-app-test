from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException

from velowind_appium.actions import find_visible_text_if_present, tap_if_present, tap_text_if_present


class StubElement:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class AndroidStubDriver:
    capabilities = {"platformName": "Android"}

    def __init__(self, expected_text: str):
        self.expected_text = expected_text
        self.element = StubElement()
        self.locators = []

    def find_element(self, by, value):
        self.locators.append((by, value))
        if by == AppiumBy.ANDROID_UIAUTOMATOR and self.expected_text in value:
            return self.element
        raise NoSuchElementException("no match")


def test_find_visible_text_uses_android_uiautomator_for_android_sessions():
    driver = AndroidStubDriver("首页")

    assert find_visible_text_if_present(driver, ["首页"]) == "首页"
    assert driver.locators == [
        (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("首页")'),
    ]


def test_tap_text_uses_android_uiautomator_for_android_sessions():
    driver = AndroidStubDriver("同意并继续")

    assert tap_text_if_present(driver, "同意并继续", timeout=0.1) is True
    assert driver.element.clicked is True


def test_tap_test_id_uses_android_resource_id_for_android_sessions():
    class AndroidIdDriver(AndroidStubDriver):
        def find_element(self, by, value):
            self.locators.append((by, value))
            if by == AppiumBy.XPATH and '@resource-id="post-home-feed-category-pager"' in value:
                return self.element
            raise NoSuchElementException("no match")

    driver = AndroidIdDriver("unused")

    assert tap_if_present(driver, "post-home-feed-category-pager", timeout=0.1) is True
    assert driver.element.clicked is True
