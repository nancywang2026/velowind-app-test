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


def test_android_note_card_reader_accepts_tall_two_column_cards():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup bounds="[15,363][633,1553]">
        <android.view.ViewGroup bounds="[15,363][633,1184]">
          <android.widget.ImageView resource-id="image" bounds="[15,363][633,1184]" />
        </android.view.ViewGroup>
        <android.widget.TextView text="长白山真的有种让人瞬间安静下来的魔力" bounds="[36,1205][612,1337]" />
        <android.widget.TextView text="#旅行日记" bounds="[63,1376][219,1418]" />
        <android.widget.ImageView resource-id="image" bounds="[36,1468][90,1522]" />
        <android.widget.TextView text="Nancy" bounds="[105,1471][456,1519]" />
        <android.widget.TextView text="赞" bounds="[552,1471][591,1519]" />
      </android.view.ViewGroup>
    </hierarchy>
    """

    assert note_card_picker._note_card_rects_from_source(page_source) == [(15, 363, 618, 1190)]


def test_android_note_card_reader_accepts_card_with_like_icon_without_like_text():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup bounds="[648,363][1265,1552]">
        <android.view.ViewGroup bounds="[648,363][1265,1183]">
          <android.widget.ImageView resource-id="image" bounds="[648,363][1265,1183]" />
        </android.view.ViewGroup>
        <android.widget.TextView text="长白山真的有种让人瞬间安静下来的魔力" bounds="[669,1204][1244,1336]" />
        <android.widget.TextView text="#长白山" bounds="[696,1375][819,1417]" />
        <android.widget.ImageView resource-id="image" bounds="[669,1467][723,1521]" />
        <android.widget.TextView text="Nancy" bounds="[738,1470][1105,1518]" />
        <android.view.ViewGroup bounds="[1127,1456][1245,1531]">
          <com.horcrux.svg.SvgView bounds="[1148,1471][1193,1516]" />
        </android.view.ViewGroup>
      </android.view.ViewGroup>
    </hierarchy>
    """

    assert note_card_picker._note_card_rects_from_source(page_source) == [(648, 363, 617, 1189)]
