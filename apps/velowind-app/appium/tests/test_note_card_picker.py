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


def test_tap_note_card_at_ordinal_reads_android_card_bounds():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup bounds="[11,306][535,957]">
        <android.widget.ImageView resource-id="image" bounds="[11,306][535,699]" />
        <android.widget.TextView text="第一条骑行笔记" bounds="[29,718][516,774]" />
        <android.widget.TextView text="用户 admin" bounds="[87,888][385,928]" />
      </android.view.ViewGroup>
      <android.view.ViewGroup bounds="[545,306][1069,957]">
        <android.widget.ImageView resource-id="image" bounds="[545,306][1069,699]" />
        <android.widget.TextView text="第二条徒步笔记" bounds="[563,718][1050,774]" />
        <android.widget.TextView text="用户 nancy" bounds="[621,888][919,928]" />
      </android.view.ViewGroup>
    </hierarchy>
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
    assert taps == [("mobile: tap", {"x": 807, "y": 709})]


def test_tap_note_card_reads_android_author_without_user_prefix():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup bounds="[11,306][535,1260]">
        <android.view.ViewGroup bounds="[11,306][535,1002]">
          <android.widget.ImageView resource-id="image" bounds="[11,306][535,1002]" />
        </android.view.ViewGroup>
        <android.widget.TextView text="故宫的红墙金瓦" bounds="[29,1021][516,1077]" />
        <android.widget.TextView text="#北京故宫" bounds="[53,1110][190,1145]" />
        <android.widget.ImageView resource-id="image" bounds="[29,1187][76,1234]" />
        <android.widget.TextView text="Nancy" bounds="[87,1191][385,1231]" />
        <android.widget.TextView text="赞" bounds="[466,1191][498,1231]" />
      </android.view.ViewGroup>
    </hierarchy>
    """
    taps = []

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((script, payload))

    assert note_card_picker.tap_note_card_at_ordinal(
        FakeDriver(),
        ordinal=1,
        page_source=page_source,
        verify_open=lambda: bool(taps),
    ) is True
    assert taps == [("mobile: tap", {"x": 273, "y": 897})]
