import pytest
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

from velowind_appium.actions import (
    LocatorTimeoutError,
    accessibility_id,
    find_first,
    tap_first,
    text,
    wait_for_first,
)


class FakeElement:
    def __init__(self, name):
        self.name = name
        self.clicks = 0

    def click(self):
        self.clicks += 1


class FakeDriver:
    capabilities = {"platformName": "iOS"}

    def __init__(self, elements=None, page_source="<App />"):
        self.elements = elements or {}
        self.page_source = page_source
        self.calls = []

    def find_element(self, by, value):
        self.calls.append((by, value))
        try:
            return self.elements[(by, value)]
        except KeyError as error:
            raise NoSuchElementException(value) from error


def test_find_first_prefers_accessibility_id_before_text():
    element = FakeElement("by-id")
    driver = FakeDriver({("accessibility id", "note-submit-button"): element})

    found = find_first(
        driver,
        [accessibility_id("note-submit-button"), text("提交审核")],
        logical_name="note submit",
    )

    assert found is element
    assert len(driver.calls) == 1


def test_wait_for_first_attempts_all_candidates_in_one_poll_cycle():
    driver = FakeDriver()

    assert wait_for_first(
        driver,
        [accessibility_id("missing-a"), accessibility_id("missing-b")],
        logical_name="missing control",
        timeout=0,
        required=False,
    ) is None
    assert [value for _, value in driver.calls] == ["missing-a", "missing-b"]


def test_required_wait_describes_candidates_and_page_summary():
    driver = FakeDriver(page_source='<XCUIElementTypeButton name="发布笔记" />')

    with pytest.raises(LocatorTimeoutError) as captured:
        wait_for_first(
            driver,
            [accessibility_id("note-title-input"), text("添加标题")],
            logical_name="note title",
            timeout=0,
        )

    message = str(captured.value)
    assert "note title" in message
    assert "note-title-input" in message
    assert "添加标题" in message
    assert "发布笔记" in message


def test_tap_first_clicks_found_element():
    element = FakeElement("submit")
    driver = FakeDriver({("accessibility id", "note-submit-button"): element})

    assert tap_first(
        driver,
        [accessibility_id("note-submit-button")],
        logical_name="note submit",
        timeout=0,
    ) is True
    assert element.clicks == 1


def test_wait_for_first_continues_after_stale_candidate():
    element = FakeElement("fallback")

    class StaleThenFallbackDriver(FakeDriver):
        def find_element(self, by, value):
            self.calls.append((by, value))
            if value == "stale":
                raise StaleElementReferenceException(value)
            if value == "fallback":
                return element
            raise NoSuchElementException(value)

    driver = StaleThenFallbackDriver()
    assert wait_for_first(
        driver,
        [accessibility_id("stale"), accessibility_id("fallback")],
        timeout=0,
    ) is element

