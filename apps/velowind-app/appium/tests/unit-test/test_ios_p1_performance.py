from unittest.mock import Mock

import pytest
from selenium.common.exceptions import WebDriverException

from velowind_appium import ios_keyboard
from velowind_appium.modules import activity, activity_sessions, message_detail, photo_picker


# Reduced from the failed physical-device hierarchy: cover, content, actions.
def activity_card(*, approved=True, listed=True, y=397, visible="true"):
    return f'''
    <XCUIElementTypeOther visible="{visible}" x="13" y="{y}" width="376" height="99">
      <XCUIElementTypeOther visible="true" />
      <XCUIElementTypeOther visible="true">
        <XCUIElementTypeOther visible="true">
          <XCUIElementTypeStaticText name="测试活动" visible="true" />
          <XCUIElementTypeOther name="{'通过' if approved else '审核中'}" visible="true" />
          <XCUIElementTypeOther name="{'上架' if listed else '下架'}" visible="true" />
        </XCUIElementTypeOther>
      </XCUIElementTypeOther>
      <XCUIElementTypeOther visible="true">
        <XCUIElementTypeOther visible="true" enabled="true" x="347" y="{y + 7}" width="34" height="34" />
      </XCUIElementTypeOther>
    </XCUIElementTypeOther>'''


def activity_list(cards):
    return f'''<AppiumAUT>
    <XCUIElementTypeWindow visible="true" x="0" y="0" width="402" height="874">
      <XCUIElementTypeScrollView visible="true" x="0" y="220" width="402" height="654">
        {cards}
      </XCUIElementTypeScrollView>
    </XCUIElementTypeWindow></AppiumAUT>'''


def test_ios_more_requires_both_states_on_same_visible_card():
    cards = (activity_card(approved=False, y=240)
             + activity_card(listed=False, y=347)
             + activity_card(y=454))
    assert activity_sessions._ios_approved_more_point(activity_list(cards)) == (364, 478)


@pytest.mark.parametrize("cards", [
    activity_card(approved=False) + activity_card(listed=False),
    activity_card(visible="false"), activity_card(y=-100), activity_card(y=900),
])
def test_ios_more_rejects_ineligible_or_offscreen_cards(cards):
    assert activity_sessions._ios_approved_more_point(activity_list(cards)) is None


def test_ios_more_respects_hidden_ancestor():
    source = activity_list(activity_card()).replace('XCUIElementTypeScrollView visible="true"',
                                                   'XCUIElementTypeScrollView visible="false"')
    assert activity_sessions._ios_approved_more_point(source) is None


def test_ios_scroll_and_select_uses_one_snapshot_per_screen(monkeypatch):
    sources = iter([activity_list(activity_card(approved=False)), activity_list(activity_card())])
    reads = []
    def read(driver):
        reads.append(True)
        return next(sources)
    monkeypatch.setattr(activity_sessions, "_safe_page_source", read)
    menu = Mock(return_value=True)
    monkeypatch.setattr(activity_sessions, "tap_text_if_present", menu)
    driver = Mock(capabilities={"platformName": "iOS"})
    activity_sessions.open_manage_sessions_for_approved_activity(driver, timeout=10)
    assert len(reads) == 2
    assert [call.args[0] for call in driver.execute_script.call_args_list] == [
        "mobile: dragFromToForDuration", "mobile: tap",
    ]
    assert driver.execute_script.call_args_list[-1].args[1] == {"x": 364, "y": 421}
    driver.find_elements.assert_not_called()
    menu.assert_called_once()


def test_android_manage_navigation_does_not_enter_ios_path(monkeypatch):
    monkeypatch.setattr(activity_sessions, "_open_ios_manage_sessions", Mock(side_effect=AssertionError("iOS path")))
    monkeypatch.setattr(activity_sessions, "_safe_page_source", lambda driver: "管理场次")
    menu = Mock(return_value=True)
    monkeypatch.setattr(activity_sessions, "tap_text_if_present", menu)
    activity_sessions.open_manage_sessions_for_approved_activity(Mock(capabilities={"platformName": "Android"}))
    menu.assert_called_once()


def note_source(counts):
    entries = ''.join(f'''<XCUIElementTypeOther name="{count}" visible="true"
      x="{204 + index * 65}" y="813" width="55" height="26">
        <XCUIElementTypeOther visible="true" x="{204 + index * 65}" y="813" width="26" height="26" />
        <XCUIElementTypeStaticText name="{count}" visible="true"
          x="{232 + index * 65}" y="814" width="27" height="24" />
      </XCUIElementTypeOther>''' for index, count in enumerate(counts))
    # Retained feed data must never satisfy the post-interaction assertion.
    return f'''<AppiumAUT><XCUIElementTypeOther name="用户 99 88 77" />
      <XCUIElementTypeOther name="post-detail-page" visible="true">
        <XCUIElementTypeOther name="{' '.join(counts)}" visible="true">{entries}</XCUIElementTypeOther>
      </XCUIElementTypeOther></AppiumAUT>'''


@pytest.mark.parametrize("action,index", [(message_detail.like_note, 0), (message_detail.favorite_note, 1)])
def test_ios_action_reuses_initial_source_and_checks_fresh_counts(action, index):
    class Driver:
        capabilities = {"platformName": "iOS"}
        reads = 0
        counts = ["0", "0", "0"]
        @property
        def page_source(self):
            self.reads += 1
            return note_source(self.counts)
        def execute_script(self, script, payload):
            assert script == "mobile: tap"
            assert payload == {"x": 217 + index * 65, "y": 826}
            self.counts = self.counts.copy()
            self.counts[index] = "1"
        def find_elements(self, *args):
            raise AssertionError("Must not scan every XCUIElementTypeOther")
    driver = Driver()
    before, after = action(driver, timeout=1)
    assert before == ["0", "0", "0"]
    assert after[index] == "1"
    assert driver.reads == 2


def test_ios_counts_are_from_active_detail():
    assert message_detail.parse_detail_snapshot(note_source(["1", "2", "3"])).bottom_action_counts == ["1", "2", "3"]


def test_ios_retry_taps_current_action_center_without_element_scan():
    driver = Mock(capabilities={"platformName": "iOS"}, page_source=note_source(["1", "2", "3"]))
    assert message_detail._tap_bottom_action_element_center_at_index(driver, 1)
    driver.execute_script.assert_called_once_with("mobile: tap", {"x": 296, "y": 826})
    driver.find_elements.assert_not_called()


@pytest.mark.parametrize("module", [activity, message_detail])
def test_ios_absent_keyboard_needs_no_hide_attempt(module):
    driver = Mock(capabilities={"platformName": "iOS"})
    driver.is_keyboard_shown.return_value = False
    module._hide_keyboard(driver)
    driver.hide_keyboard.assert_not_called()
    driver.execute_script.assert_not_called()


def test_ios_keyboard_checks_actual_result():
    driver = Mock()
    driver.is_keyboard_shown.side_effect = [True, False]
    assert ios_keyboard.hide_ios_keyboard_if_possible(driver)
    assert driver.execute_script.call_args.args[1]["keys"][0] == "完成"
    driver.is_keyboard_shown.side_effect = [True, True]
    assert not ios_keyboard.hide_ios_keyboard_if_possible(driver)


@pytest.mark.parametrize("module", [activity, message_detail])
def test_ios_keyboard_failure_keeps_page_fallback(module, monkeypatch):
    driver = Mock(capabilities={"platformName": "iOS"})
    driver.is_keyboard_shown.return_value = True
    driver.execute_script.side_effect = WebDriverException("No dismissal key")
    fallback = Mock()
    monkeypatch.setattr(module, "_dismiss_keyboard_with_safe_tap", fallback)
    module._hide_keyboard(driver)
    fallback.assert_called_once_with(driver)
    assert driver.execute_script.call_count == 1


@pytest.mark.parametrize("module", [activity, message_detail])
def test_android_keyboard_retains_original_native_call(module):
    driver = Mock(capabilities={"platformName": "Android"})
    module._hide_keyboard(driver)
    driver.hide_keyboard.assert_called_once_with()
    driver.is_keyboard_shown.assert_not_called()
    driver.execute_script.assert_not_called()


@pytest.mark.parametrize("attributes", [
    'name="Add" label="完成" enabled="true" visible="true"',
    'enabled="true" visible="true" x="340" y="120" name="Add" label="完成"',
])
def test_ios_photo_selection_does_not_depend_on_attribute_order(attributes):
    source = f'<AppiumAUT><XCUIElementTypeButton {attributes} /></AppiumAUT>'
    driver = Mock(capabilities={"platformName": "iOS"})
    assert photo_picker._photo_picker_done_button_enabled(driver, page_source=source)
    driver.find_element.assert_not_called()
    assert not photo_picker._photo_picker_done_button_enabled(driver, page_source=source.replace('enabled="true"', 'enabled="false"'))


@pytest.mark.parametrize("name,probe", [
    ("确认裁剪", message_detail._cropper_visible),
    ("确认裁剪", photo_picker._cropper_visible),
    ("标记地点", message_detail._location_section_visible),
    ("搜索地点", message_detail._location_picker_visible),
])
def test_ios_page_states_handle_json_serialized_xml_and_hidden_ancestors(name, probe):
    node = f'<XCUIElementTypeOther enabled="true" visible="true" x="10" name="{name}" />'
    assert probe(f'<AppiumAUT>{node}</AppiumAUT>')
    assert not probe(f'<AppiumAUT><XCUIElementTypeOther visible="false">{node}</XCUIElementTypeOther></AppiumAUT>')


def test_ios_itinerary_count_includes_filled_and_scrolled_off_sections():
    def section(visible):
        return f'''<XCUIElementTypeOther visible="{visible}">
          <XCUIElementTypeOther><XCUIElementTypeTextField value="第一天" /></XCUIElementTypeOther>
          <XCUIElementTypeOther><XCUIElementTypeTextField value="集合" /></XCUIElementTypeOther>
          <XCUIElementTypeOther><XCUIElementTypeTextView value="行程正文" /></XCUIElementTypeOther>
        </XCUIElementTypeOther>'''
    before = f'<AppiumAUT>{section("true")}</AppiumAUT>'
    after = f'<AppiumAUT>{section("false")}{section("true")}</AppiumAUT>'
    assert activity._count_itinerary_editor_sections(before) == 1
    assert activity._count_itinerary_editor_sections(after) == 2


def test_ios_empty_itinerary_title_supports_json_source_without_placeholder():
    source = '<AppiumAUT><XCUIElementTypeTextField enabled="true" visible="true" value="标题" /></AppiumAUT>'
    assert activity._count_itinerary_editor_sections(source) == 1


def test_ios_location_results_remain_detectable_after_query_replaces_placeholder():
    source = '''<AppiumAUT>
      <XCUIElementTypeOther enabled="true" visible="true" name="activity-session-create-poi-search-drawer-header" />
      <XCUIElementTypeTextField enabled="true" visible="true" value="张家界景区" />
      <XCUIElementTypeScrollView visible="true">
        <XCUIElementTypeStaticText visible="true" value="张家界国家森林公园" />
      </XCUIElementTypeScrollView>
    </AppiumAUT>'''
    assert activity_sessions._session_location_modal_visible(source)
    assert activity_sessions._session_location_results_visible(source, "张家界景区")
    assert not activity_sessions._session_location_results_visible(source.replace('value="张家界国家森林公园"', 'value="搜索中"'), "张家界景区")
