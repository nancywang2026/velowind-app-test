from velowind_appium.modules import note_card_picker


def test_tap_note_card_at_ordinal_selects_second_unique_card():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="第一条骑行笔记 用户 admin" x="8" y="180" width="188" height="260" />
      <XCUIElementTypeOther name="第一条骑行笔记 用户 admin" x="8" y="180" width="188" height="260" />
      <XCUIElementTypeOther name="第一条骑行笔记 用户 admin" x="8" y="300" width="188" height="100" />
      <XCUIElementTypeOther name="第二条徒步笔记 用户 nancy" x="206" y="180" width="188" height="260" />
    </AppiumAUT>
    """
    taps = []

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert note_card_picker.tap_note_card_at_ordinal(
        FakeDriver(),
        ordinal=2,
        page_source=page_source,
        verify_open=lambda: bool(taps),
    ) is True
    assert taps == [("mobile: tap", {"x": 300, "y": 341})]


def test_tap_note_card_at_ordinal_rejects_non_positive_ordinal():
    try:
        note_card_picker.tap_note_card_at_ordinal(object(), ordinal=0)
    except ValueError as error:
        assert str(error) == "Note card ordinal must be at least 1"
    else:
        raise AssertionError("Expected a non-positive ordinal to be rejected")
