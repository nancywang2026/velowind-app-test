from velowind_appium.modules import home_feed


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
