import pytest
from selenium.common.exceptions import TimeoutException

from velowind_appium.modules import home_feed


def test_tap_first_message_binds_driver_to_detail_verifier(monkeypatch):
    driver = object()
    verified_drivers = []

    monkeypatch.setattr(
        home_feed,
        "message_detail_is_visible",
        lambda actual_driver: verified_drivers.append(actual_driver) or True,
    )

    def fake_tap_first_note_card(actual_driver, *, verify_open):
        assert actual_driver is driver
        return verify_open()

    monkeypatch.setattr(home_feed, "tap_first_note_card", fake_tap_first_note_card)

    assert home_feed._tap_first_message(driver) is True
    assert verified_drivers == [driver]


def test_tap_first_visible_card_binds_driver_to_detail_verifier(monkeypatch):
    driver = object()
    verified_drivers = []

    monkeypatch.setattr(
        home_feed,
        "message_detail_is_visible",
        lambda actual_driver: verified_drivers.append(actual_driver) or True,
    )

    def fake_tap_first_note_card(actual_driver, *, verify_open):
        assert actual_driver is driver
        return verify_open()

    monkeypatch.setattr(home_feed, "tap_first_note_card", fake_tap_first_note_card)

    assert home_feed._tap_first_visible_card(driver) is True
    assert verified_drivers == [driver]


def test_open_first_home_message_waits_for_detail_after_tap(monkeypatch):
    state = {"detail_visible": False}
    clock = {"now": 0.0}

    monkeypatch.setattr(home_feed, "wait_for_home_feed", lambda driver, timeout=60: True)
    monkeypatch.setattr(home_feed, "_tap_first_message", lambda driver: True)
    monkeypatch.setattr(home_feed, "_tap_first_visible_card", lambda driver: False)
    monkeypatch.setattr(home_feed, "swipe_vertical", lambda driver, direction="up": None)
    monkeypatch.setattr(home_feed.time, "monotonic", lambda: clock["now"])

    def fake_sleep(seconds):
        clock["now"] += seconds
        if clock["now"] >= 0.4:
            state["detail_visible"] = True

    monkeypatch.setattr(home_feed.time, "sleep", fake_sleep)
    monkeypatch.setattr(home_feed, "message_detail_is_visible", lambda driver: state["detail_visible"])

    home_feed.open_first_home_message(object())


def test_open_first_home_message_uses_card_tap_when_direct_target_missing(monkeypatch):
    events = []

    monkeypatch.setattr(home_feed, "wait_for_home_feed", lambda driver, timeout=60: True)
    monkeypatch.setattr(home_feed, "message_detail_is_visible", lambda driver: False)
    monkeypatch.setattr(home_feed, "_tap_first_message", lambda driver: False)
    monkeypatch.setattr(home_feed, "_tap_first_visible_card", lambda driver: events.append("tap-card") or True)
    monkeypatch.setattr(home_feed, "swipe_vertical", lambda driver, direction="up": events.append(f"swipe-{direction}"))
    monotonic_values = iter([0, 1, 2, 3, 4, 5, 6])
    monkeypatch.setattr(home_feed.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(home_feed.time, "sleep", lambda seconds: None)

    try:
        home_feed.open_first_home_message(object(), max_swipes=0)
    except AssertionError:
        pass

    assert "tap-card" in events


def test_wait_for_home_feed_ignores_message_detail_overlay(monkeypatch):
    page_states = iter(
        [
            "首页 全国 写留言 post-detail-banner-pager",
            "post-home-feed-category-pager 首页 全国 推荐",
        ]
    )

    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: next(page_states))
    monkeypatch.setattr(home_feed, "_home_ready_id_present", lambda driver: False)
    monotonic_values = iter([0, 1, 2, 3, 4])
    monkeypatch.setattr(home_feed.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(home_feed.time, "sleep", lambda seconds: None)

    assert home_feed.wait_for_home_feed(object(), timeout=3) == "home-feed-text"


def test_wait_for_home_feed_ignores_activity_detail_overlay(monkeypatch):
    page_states = iter(
        [
            "首页 全国 活动详情 activity-route-detail-v3-hero-carousel 页面预览提示",
            "post-home-feed-category-pager 首页 全国 推荐",
        ]
    )

    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: next(page_states))
    monkeypatch.setattr(home_feed, "_home_ready_id_present", lambda driver: False)
    monotonic_values = iter([0, 1, 2, 3, 4])
    monkeypatch.setattr(home_feed.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(home_feed.time, "sleep", lambda seconds: None)

    assert home_feed.wait_for_home_feed(object(), timeout=3) == "home-feed-text"


def test_wait_for_home_feed_accepts_android_test_id_without_home_label(monkeypatch):
    page_source = '<android.widget.FrameLayout resource-id="post-home-feed-category-pager" />'
    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(home_feed, "_home_ready_id_present", lambda driver: False)

    assert home_feed.wait_for_home_feed(object(), timeout=0.1) == "home-feed-text"


def test_wait_for_home_feed_rejects_android_note_search_overlay(monkeypatch):
    page_source = """
    <hierarchy>
      <android.widget.EditText text="骑行" hint="请输入内容" displayed="true" />
      <android.widget.FrameLayout
        resource-id="post-home-feed-category-pager"
        displayed="true"
      />
    </hierarchy>
    """
    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(home_feed, "_home_ready_id_present", lambda driver: False)

    with pytest.raises(TimeoutException, match="Home feed did not become ready"):
        home_feed.wait_for_home_feed(object(), timeout=0.01)


def test_note_feed_accepts_android_results_when_a_visible_card_matches_type():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="骑行" displayed="true" />
      <android.widget.TextView text="沿途有风" displayed="true" />
      <android.widget.TextView text="#骑行" displayed="true" />
      <android.widget.TextView text="湖边慢走" displayed="true" />
      <android.widget.TextView text="#徒步" displayed="true" />
    </hierarchy>
    """

    assert home_feed.note_feed_all_results_match_type(page_source, "骑行") == (True, [])


def test_note_feed_accepts_android_results_when_selected_type_has_nonempty_cards():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup selected="true" displayed="true">
        <android.widget.TextView text="骑行" displayed="true" />
      </android.view.ViewGroup>
      <android.widget.TextView text="#云南洱海" displayed="true" />
    </hierarchy>
    """

    assert home_feed.note_feed_all_results_match_type(page_source, "骑行") == (True, [])


def test_switch_note_type_navigation_accepts_android_root_without_home_label(monkeypatch):
    page_source = (
        '<android.widget.FrameLayout resource-id="post-home-feed-category-pager" /> '
        '<android.widget.TextView text="全国" /> <android.widget.TextView text="骑行" />'
    )
    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: page_source)

    home_feed.switch_note_type_navigation(object(), timeout=0.1)


def test_note_feed_contains_type_results_requires_card_content():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="全国" />
      <XCUIElementTypeStaticText name="徒步" />
      <XCUIElementTypeOther name="莫干山山间徒步很舒服 用户 abc 赞" />
    </AppiumAUT>
    """

    assert home_feed.note_feed_contains_type_results(page_source, "徒步") is True
    assert home_feed.note_feed_type_result_texts(page_source, "徒步") == [
        "莫干山山间徒步很舒服 用户 abc 赞"
    ]


def test_note_feed_contains_type_results_does_not_require_interaction_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="骑行" />
      <XCUIElementTypeOther name="【API复测】沿途有风 0714-1205 #骑行 用户 admin" />
    </AppiumAUT>
    """

    assert home_feed.note_feed_contains_type_results(page_source, "骑行") is True
    assert home_feed.note_feed_type_result_texts(page_source, "骑行") == [
        "【API复测】沿途有风 0714-1205 #骑行 用户 admin"
    ]


def test_note_feed_contains_type_results_rejects_navigation_only():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="全国" />
      <XCUIElementTypeStaticText name="徒步" />
      <XCUIElementTypeStaticText name="骑行" />
    </AppiumAUT>
    """

    assert home_feed.note_feed_contains_type_results(page_source, "徒步") is False


def test_note_feed_all_results_match_type_rejects_mixed_visible_cards():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="莫干山山间徒步很舒服 用户 abc 赞" />
      <XCUIElementTypeOther name="良渚古城遛娃太好逛了 用户 def 赞" />
    </AppiumAUT>
    """

    all_results_match, mismatched = home_feed.note_feed_all_results_match_type(page_source, "徒步")

    assert all_results_match is False
    assert mismatched == ["良渚古城遛娃太好逛了 用户 def 赞"]


def test_note_feed_all_results_match_type_accepts_all_visible_cards():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="莫干山山间徒步很舒服 用户 abc 赞" />
      <XCUIElementTypeOther name="断桥附近散步路线记录 用户 def 浏览" />
    </AppiumAUT>
    """

    assert home_feed.note_feed_all_results_match_type(page_source, "徒步") == (True, [])


def test_note_feed_all_results_match_type_ignores_container_and_user_rows():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="徒步的一天 用户 abc 赞 良渚古城遛娃太好逛了 用户 def 赞" />
      <XCUIElementTypeOther name="用户 abc 赞" />
      <XCUIElementTypeOther name="徒步的一天 用户 abc 赞" />
    </AppiumAUT>
    """

    assert home_feed.note_feed_all_results_match_type(page_source, "徒步") == (True, [])


def test_select_note_type_waits_for_type_results(monkeypatch):
    events = []
    page_states = iter(["首页 全国 推荐 徒步", "首页 全国 推荐 徒步 莫干山徒步 用户 abc 赞"])

    monkeypatch.setattr(home_feed, "_tap_note_type", lambda driver, type_name: events.append(type_name) or True)
    monkeypatch.setattr(home_feed, "_safe_page_source", lambda driver: next(page_states))
    monotonic_values = iter([0, 0.2, 0.4, 1.2])
    monkeypatch.setattr(home_feed.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(home_feed.time, "sleep", lambda seconds: None)

    home_feed.select_note_type(object(), "徒步", timeout=1)

    assert events == ["徒步"]
