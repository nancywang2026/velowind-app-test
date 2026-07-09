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
