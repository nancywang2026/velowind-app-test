"""Reduced hierarchy from 20261109-174955-98455; no user content retained."""
from unittest.mock import Mock

import pytest

from velowind_appium.modules import message_detail


ACTION_IDS = (
    "post-detail-bottom-like-action",
    "post-detail-bottom-favorite-action",
    "post-detail-bottom-comment-action",
)


def source(counts=("2", "1", "1"), *, y=796, visible="true", enabled="true"):
    actions = "".join(
        f'<XCUIElementTypeOther name="{name}" label="{count}" '
        f'visible="{visible}" enabled="{enabled}" x="{204 + index * 65}" y="{y}" width="55" height="26">'
        f'<XCUIElementTypeStaticText name="{count}" label="{count}" visible="{visible}" enabled="{enabled}" '
        f'x="{232 + index * 65}" y="{y + 1}" width="27" height="24" />'
        '</XCUIElementTypeOther>'
        for index, (name, count) in enumerate(zip(ACTION_IDS, counts))
    )
    return (
        '<AppiumAUT><XCUIElementTypeOther name="用户 99 88 77" />'
        '<XCUIElementTypeOther name="post-detail-page" visible="true">'
        '<XCUIElementTypeOther name="post-detail-bottom-bar" label="2 1 1" visible="true">'
        f'{actions}</XCUIElementTypeOther></XCUIElementTypeOther></AppiumAUT>'
    )


@pytest.mark.parametrize("action,index", [(message_detail.like_note, 0), (message_detail.favorite_note, 1)])
@pytest.mark.parametrize("y", [796, 650])
def test_identified_action_uses_label_count_and_actual_bounds(action, index, y):
    before = ["2", "1", "1"]
    after = before.copy()
    after[index] = str(int(after[index]) + 1)
    driver = Mock(capabilities={"platformName": "iOS"})
    type(driver).page_source = property(Mock(side_effect=[source(before, y=y), source(after, y=y)]))

    assert action(driver, timeout=1) == (before, after)
    driver.execute_script.assert_called_once_with("mobile: tap", {"x": 217 + index * 65, "y": y + 13})
    driver.find_elements.assert_not_called()


def test_count_center_retry_uses_identified_action_bounds():
    driver = Mock(capabilities={"platformName": "iOS"}, page_source=source())
    assert message_detail._tap_bottom_action_element_center_at_index(driver, 1)
    driver.execute_script.assert_called_once_with("mobile: tap", {"x": 296, "y": 809})


@pytest.mark.parametrize("attrs", [{"visible": "false"}, {"enabled": "false"}])
def test_hidden_or_disabled_actions_are_not_tapped(attrs):
    driver = Mock(capabilities={"platformName": "iOS"}, page_source=source(**attrs))
    assert not message_detail._tap_ios_bottom_action_by_source(driver, 0)
    driver.execute_script.assert_not_called()


def test_successful_tap_still_requires_count_change(monkeypatch):
    driver = Mock(capabilities={"platformName": "iOS"}, page_source=source())
    monkeypatch.setattr(message_detail, "_wait_for_bottom_action_count_change", Mock(return_value=None))
    with pytest.raises(AssertionError, match="did not change"):
        message_detail.like_note(driver, timeout=1)
    assert driver.execute_script.call_count == 2
