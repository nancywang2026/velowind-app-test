from __future__ import annotations

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

from .core import Blocked, require


class NativeUI:
    """Named operations execute ordinary Appium instructions, never a mock bridge.

    Each configured locator requires its XML/device evidence reference. Runtime
    parameters are substituted as literal accessibility identifiers or exact
    text, not interpolated into XPath or arbitrary executable predicate code.
    """
    def __init__(self, driver, bindings, *, timeout=20):
        self.driver, self.bindings, self.timeout = driver, bindings, timeout

    def locator(self, key, values):
        entry = self.bindings.get(key)
        if not entry or not entry.get("evidence"):
            raise Blocked(f"Unverified UI locator: {key}")
        value = entry["value"].format_map(values)
        strategy = entry.get("by", "accessibility id")
        if strategy == "text":
            # Exact text predicate generated with escaping; no guessed coordinates.
            literal = value.replace("\\", "\\\\").replace('"', '\\"')
            return AppiumBy.IOS_PREDICATE, f'name == "{literal}" OR label == "{literal}"'
        if strategy != "accessibility id": raise Blocked("Only verified accessibility ID/exact text locators supported")
        return AppiumBy.ACCESSIBILITY_ID, value

    def elements(self, key, **values):
        return [e for e in self.driver.find_elements(*self.locator(key, values)) if e.is_displayed()]

    def one(self, key, **values):
        def find(_):
            rows = self.elements(key, **values)
            require(len(rows) <= 1, f"Ambiguous UI locator: {key}")
            return rows[0] if rows else False
        return WebDriverWait(self.driver, self.timeout, poll_frequency=.5,
            ignored_exceptions=(NoSuchElementException, StaleElementReferenceException)).until(find, key)

    def action(self, kind, key=None, *, value=None, **values):
        if kind == "back": return self.driver.back()
        if kind == "restart":
            if not value: raise Blocked("Explicit App bundle ID needed for restart")
            self.driver.terminate_app(value); self.driver.activate_app(value); return
        element = self.one(key, **values)
        if kind == "click": element.click()
        elif kind == "input": element.click(); element.clear(); element.send_keys(str(value))
        elif kind == "visible": return True
        elif kind == "value": return element.get_attribute("value") or element.text
        elif kind == "enabled": return element.is_enabled()
        elif kind == "rect": return dict(element.rect)
        elif kind == "hold": self.driver.execute_script("mobile: touchAndHold", {"elementId": element.id, "duration": 1})
        elif kind == "scroll":
            require(value in {"up", "down"}, "Invalid scroll direction")
            self.driver.execute_script("mobile: scroll", {"elementId": element.id, "direction": value})
        else: raise Blocked(f"Unknown native operation: {kind}")

    def contained_above(self, message_key, composer_key, **values):
        message = self.one(message_key, **values).rect
        composer = self.one(composer_key, **values).rect
        screen = self.driver.get_window_size()
        require(message["y"] >= 0 and message["height"] > 0, "Latest message is not on screen")
        require(message["y"] + message["height"] <= min(composer["y"], screen["height"]),
                "Latest message obscured by composer/keyboard or below viewport")
