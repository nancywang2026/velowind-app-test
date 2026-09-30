from types import SimpleNamespace

import pytest
from selenium.common.exceptions import WebDriverException

from velowind_appium.modules import activity_sessions as sessions


@pytest.mark.parametrize('labels,expected', [
    (['10月1日11点05分'], {'month': '10', 'day': '01', 'hour': '11', 'minute': '05'}),
    (['9月26日11点'], {'month': '09', 'day': '26', 'hour': '11', 'minute': '00'}),
    ([], None),
    (['9月26日11点', '10月1日11点'], None),
    (['已选择时间 9月26日11点 旧页面 6月30日10点'], None),
])
def test_selected_label_requires_one_exact_visible_date(labels, expected):
    queries = []

    def find_elements(by, query):
        queries.append((by, query))
        return [SimpleNamespace(get_attribute=lambda attr, label=label: label) for label in labels]

    driver = SimpleNamespace(find_elements=find_elements)
    assert sessions._ios_datetime_picker_selected_parts(driver) == expected
    assert queries[0][0] == '-ios predicate string'
    assert 'visible == true' in queries[0][1]
    assert 'XCUIElementTypeStaticText' in queries[0][1]


def test_selected_label_driver_failure_is_fallback():
    def fail(*args):
        raise WebDriverException('stale date label')

    assert sessions._ios_datetime_picker_selected_parts(SimpleNamespace(find_elements=fail)) is None


class MovingDatePicker:
    def __init__(self):
        self.day = 10
        self.source_reads = 0
        self.swipes = []

    def get_window_rect(self):
        return {'width': 402, 'height': 874}

    @property
    def page_source(self):
        self.source_reads += 1
        return f'''<root>
          <XCUIElementTypeStaticText visible="true" label="9月{self.day}日9点00分" />
          <XCUIElementTypeStaticText visible="true" label="日" x="111" y="575" width="84" height="20" />
          <XCUIElementTypeStaticText visible="true" label="{self.day}" x="111" y="654" width="84" height="44" />
        </root>'''

    def swipe(self, x1, y1, x2, y2, **kwargs):
        self.swipes.append((x1, y1, x2, y2))
        self.day += 2 if y1 > y2 else -1


def test_wheel_reverses_after_overshoot_and_confirms_target_with_source(monkeypatch):
    driver = MovingDatePicker()
    monkeypatch.setattr(sessions.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sessions, '_ios_datetime_picker_selected_parts',
                        lambda d: {'day': f'{d.day:02d}'})
    assert sessions._tap_ios_datetime_picker_wheel_to_target(driver, 'day', '11')
    assert driver.day == 11
    assert len(driver.swipes) == 2
    assert driver.source_reads == 2


def test_lightweight_target_cannot_override_fresh_source(monkeypatch):
    driver = MovingDatePicker()
    monkeypatch.setattr(sessions.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sessions, '_ios_datetime_picker_selected_parts', lambda d: {'day': '11'})
    assert sessions._tap_ios_datetime_picker_wheel_to_target(driver, 'day', '11')
    assert driver.day == 11
    assert len(driver.swipes) == 2
    assert driver.source_reads == 3


def test_missing_lightweight_label_keeps_fresh_source_fallback(monkeypatch):
    driver = MovingDatePicker()
    monkeypatch.setattr(sessions.time, 'sleep', lambda _: None)
    monkeypatch.setattr(sessions, '_ios_datetime_picker_selected_parts', lambda d: None)
    assert sessions._tap_ios_datetime_picker_wheel_to_target(driver, 'day', '11')
    assert driver.day == 11
    assert driver.source_reads == 3
