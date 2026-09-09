from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from .config import Locators


class MessageUI:
    """Every control lookup goes through the external accessibility-ID mapping."""

    def __init__(self, driver, locators: Locators, execution: dict):
        self.driver = driver
        self.locators = locators
        self.execution = execution

    def wait(self, predicate, description):
        return WebDriverWait(
            self.driver, self.execution["page_timeout_seconds"],
            poll_frequency=self.execution["poll_seconds"],
            ignored_exceptions=(NoSuchElementException, StaleElementReferenceException),
        ).until(lambda _: predicate(), message=description)

    def elements(self, key, **parameters):
        return self.driver.find_elements(AppiumBy.ACCESSIBILITY_ID, self.locators.get(key, **parameters))

    def optional(self, key, **parameters):
        return next((e for e in self.elements(key, **parameters) if e.is_displayed()), None)

    def element(self, key, **parameters):
        return self.wait(lambda: self.optional(key, **parameters), f"Missing accessibility ID: {key}")

    def click(self, key, **parameters):
        element = self.wait(
            lambda: (e if (e := self.optional(key, **parameters)) is not None and e.is_enabled() else False),
            f"Not clickable: {key}",
        )
        element.click()

    def text(self, key, **parameters):
        element = self.element(key, **parameters)
        # Attribute reads are assertions, never alternate locator strategies.
        value = element.get_attribute("value")
        return str(value if value is not None else element.text)

    def expect_text(self, key, expected, **parameters):
        self.wait(lambda: self.text(key, **parameters) == str(expected), f"Unexpected value: {key}")

    def input(self, key, value):
        element = self.element(key)
        element.click()
        element.clear()
        element.send_keys(value)

    def home(self):
        self.click("navigation.messages")
        self.element("home.ready")

    def back(self, ready):
        self.click("navigation.back")
        self.element(ready)

    def login(self, username, password, expected_user_id):
        self.click("navigation.account")
        self.element("account.ready")
        identity = self.optional("account.identity")
        if identity is not None:
            if self.text("account.identity") == expected_user_id:
                self.home()
                return
            self.click("account.logout")
            self.click("account.logout_confirm")
        self.click("account.login")
        self.input("login.username", username)
        self.input("login.password", password)
        self.click("login.submit")
        self.element("account.ready")
        self.expect_text("account.identity", expected_user_id)
        self.home()

    def open_conversation(self, conversation_id):
        self.click("conversation.row", id=conversation_id)
        self.element("chat.ready")
        self.expect_text("chat.identity", conversation_id)

    def group_details(self):
        self.click("chat.details")
        self.element("group.ready")

    def send(self, text):
        self.click("chat.composer")
        self.input("chat.input", text)
        self.click("chat.send")

    def hold_conversation(self, conversation_id):
        element = self.element("conversation.row", id=conversation_id)
        self.driver.execute_script("mobile: touchAndHold", {
            "elementId": element.id, "duration": self.execution["hold_seconds"],
        })
        self.element("conversation.menu")

    def collection(self, name):
        """Read a complete fixture-sized list; fail rather than infer absence offscreen.

        App contract: total is the loaded server total, rows expose entity IDs via
        value, and the end marker only appears at the end of the complete list.
        Scrolling is scoped to an ID-located container, never screen coordinates.
        """
        self.element(f"{name}.ready")
        expected_total = int(self.text(f"{name}.total"))
        found = set()
        for _ in range(self.execution["max_scrolls"]):
            page = [str(e.get_attribute("value")) for e in self.elements(f"{name}.item") if e.is_displayed()]
            assert all(v and v != "None" for v in page), f"{name} row is missing entity ID value"
            assert len(page) == len(set(page)), f"Duplicate entity rows in {name}"
            found.update(page)
            if self.optional(f"{name}.end") is not None and len(found) == expected_total:
                return found
            container = self.element(f"{name}.container")
            self.driver.execute_script("mobile: scroll", {"elementId": container.id, "direction": "down"})
        raise AssertionError(f"Incomplete {name} list: collected {len(found)}, expected {expected_total}")

    def visible_message_count(self, message_id):
        return len([e for e in self.elements("chat.message", id=message_id) if e.is_displayed()])

    def toggle(self, key):
        value = self.element(key).get_attribute('value')
        if value in ('1', 'true', True):
            return True
        if value in ('0', 'false', False):
            return False
        raise AssertionError(f'{key} must expose a boolean accessibility value')

    def set_toggle(self, key, enabled):
        if self.toggle(key) != enabled:
            self.click(key)
        self.wait(lambda: self.toggle(key) == enabled, f'Toggle did not update: {key}')
