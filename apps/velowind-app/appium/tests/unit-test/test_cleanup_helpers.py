from velowind_appium.cleanup import (
    CleanupReport,
    cleanup_activities,
    cleanup_exact_visible_item,
    cleanup_notes,
    cleanup_published_note,
    cleanup_sessions,
    cleanup_matching_visible_items,
    confirm_destructive_action,
    find_matching_visible_texts,
)


def test_find_matching_visible_texts_extracts_unique_page_source_values():
    page_source = """
    <App>
      <Text text="测试 - 长白山" />
      <Text name="测试 - 长白山" />
      <Text label="普通笔记" />
      <Text value="自动化场次 0727" />
    </App>
    """

    assert find_matching_visible_texts(page_source, ["测试 -", "自动化场次"]) == [
        "测试 - 长白山",
        "自动化场次 0727",
    ]


def test_find_matching_visible_texts_skips_standalone_topic_tags():
    page_source = """
    <App>
      <Text text="#长白山" />
      <Text text="长白山真的有种让人瞬间安静下来的魔力" />
    </App>
    """

    assert find_matching_visible_texts(page_source, ["长白山"]) == [
        "长白山真的有种让人瞬间安静下来的魔力"
    ]


def test_find_matching_visible_texts_skips_ios_page_container_values():
    page_source = """
    <App>
      <XCUIElementTypeOther type="XCUIElementTypeOther" name="我的笔记 长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4 想去一趟洱海" label="我的笔记 长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4 想去一趟洱海" visible="true" />
      <XCUIElementTypeOther type="XCUIElementTypeOther" name="我的笔记 长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4 想去一趟洱海" label="我的笔记 长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4 想去一趟洱海">
        <XCUIElementTypeOther type="XCUIElementTypeOther" name="长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4" label="长白山真的有种让人瞬间安静下来的魔力 #长白山 我 0 4">
          <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" name="长白山真的有种让人瞬间安静下来的魔力" label="长白山真的有种让人瞬间安静下来的魔力" visible="true" />
          <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" name="#长白山" label="#长白山" />
        </XCUIElementTypeOther>
      </XCUIElementTypeOther>
    </App>
    """

    assert find_matching_visible_texts(page_source, ["长白山"]) == [
        "长白山真的有种让人瞬间安静下来的魔力"
    ]


def test_find_matching_visible_texts_skips_invisible_ios_texts():
    page_source = """
    <App>
      <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" name="屏幕外长白山笔记" label="屏幕外长白山笔记" visible="false" />
      <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" name="屏幕内长白山笔记" label="屏幕内长白山笔记" visible="true" />
    </App>
    """

    assert find_matching_visible_texts(page_source, ["长白山"]) == ["屏幕内长白山笔记"]


def test_confirm_destructive_action_taps_confirm_text_after_action(monkeypatch):
    events = []
    monkeypatch.setattr(
        "velowind_appium.cleanup.tap_text_if_present",
        lambda driver, text, timeout=1: events.append(text) or text == "确定",
    )

    assert confirm_destructive_action(object()) is True
    assert events == ["确认删除", "确定"]


def test_cleanup_matching_visible_items_deletes_each_matching_candidate(monkeypatch):
    class FakeDriver:
        page_source = '<Text text="测试 - 长白山" /><Text text="普通笔记" />'

    events = []
    monkeypatch.setattr(
        "velowind_appium.cleanup.tap_matching_item",
        lambda driver, text: events.append(("tap-item", text)) or True,
    )
    monkeypatch.setattr(
        "velowind_appium.cleanup.tap_first_available_text",
        lambda driver, texts: events.append(("tap-action", tuple(texts))) or True,
    )
    monkeypatch.setattr(
        "velowind_appium.cleanup.confirm_destructive_action",
        lambda driver: events.append(("confirm",)) or True,
    )

    report = cleanup_matching_visible_items(
        FakeDriver(),
        item_type="note",
        matchers=["测试 -"],
        action_texts=["删除"],
        dry_run=False,
    )

    assert report == CleanupReport(item_type="note", deleted=["测试 - 长白山"], skipped=[])
    assert events == [
        ("tap-item", "测试 - 长白山"),
        ("tap-action", ("更多", "...", "…")),
        ("tap-action", ("删除",)),
        ("confirm",),
    ]


def test_cleanup_matching_visible_items_dry_run_does_not_tap(monkeypatch):
    class FakeDriver:
        page_source = '<Text text="测试 - 长白山" />'

    monkeypatch.setattr(
        "velowind_appium.cleanup.tap_matching_item",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not tap")),
    )

    report = cleanup_matching_visible_items(
        FakeDriver(),
        item_type="note",
        matchers=["测试 -"],
        action_texts=["删除"],
        dry_run=True,
    )

    assert report == CleanupReport(item_type="note", deleted=[], skipped=["测试 - 长白山"])


def test_cleanup_matching_visible_items_scrolls_until_matching_candidate(monkeypatch):
    class FakeDriver:
        def __init__(self):
            self.index = 0
            self.sources = [
                '<Text text="普通笔记 1" />',
                '<Text text="普通笔记 2" />',
                '<Text text="测试 - 长白山" />',
            ]

        @property
        def page_source(self):
            return self.sources[self.index]

    driver = FakeDriver()
    monkeypatch.setattr(
        "velowind_appium.cleanup.swipe_vertical",
        lambda *_args, **_kwargs: setattr(driver, "index", min(driver.index + 1, 2)),
    )

    report = cleanup_matching_visible_items(
        driver,
        item_type="note",
        matchers=["测试 -"],
        action_texts=["删除"],
        dry_run=True,
        max_rounds=5,
    )

    assert report == CleanupReport(item_type="note", deleted=[], skipped=["测试 - 长白山"])


def test_cleanup_matching_visible_items_can_require_activity_status_tokens():
    class FakeDriver:
        page_source = """
        <Text text="测试 - 张家界 通过 上架" />
        <Text text="测试 - 黄山 通过 未发布" />
        <Text text="测试 - 西湖 已下架" />
        """

    report = cleanup_matching_visible_items(
        FakeDriver(),
        item_type="activity",
        matchers=["测试 -"],
        action_texts=["下架"],
        dry_run=True,
        required_texts=["通过", "上架"],
    )

    assert report == CleanupReport(item_type="activity", deleted=[], skipped=["测试 - 张家界 通过 上架"])


def test_cleanup_matching_visible_items_accepts_activity_status_as_separate_visible_text():
    class FakeDriver:
        page_source = """
        <Text text="上海出发到杭州" />
        <Text text="通过" />
        <Text text="上架" />
        """

    report = cleanup_matching_visible_items(
        FakeDriver(),
        item_type="activity",
        matchers=["上海出发到杭州"],
        action_texts=["下架"],
        dry_run=True,
        required_page_texts=["通过", "上架"],
    )

    assert report == CleanupReport(item_type="activity", deleted=[], skipped=["上海出发到杭州"])


def test_cleanup_notes_leaves_my_notes_page_after_dry_run(monkeypatch):
    events = []
    cleanup_config = type("CleanupConfig", (), {"note_matchers": ["测试 -"]})()

    monkeypatch.setattr("velowind_appium.cleanup.ensure_logged_in_on_home", lambda *args: events.append("ensure-home"))
    monkeypatch.setattr("velowind_appium.cleanup._open_me_entry", lambda driver, text: events.append(("open", text)))
    monkeypatch.setattr(
        "velowind_appium.cleanup.cleanup_matching_visible_items",
        lambda *args, **kwargs: events.append(("cleanup", kwargs["dry_run"]))
        or CleanupReport("note", [], ["测试 - 长白山"]),
    )
    monkeypatch.setattr("velowind_appium.cleanup.safe_back", lambda driver: events.append("back"))

    report = cleanup_notes(object(), cleanup_config, object(), dry_run=True)

    assert report == CleanupReport("note", [], ["测试 - 长白山"])
    assert events == ["ensure-home", ("open", "我的笔记"), ("cleanup", True), "back"]


def test_cleanup_published_note_uses_exact_title_and_leaves_my_notes_page(monkeypatch):
    events = []
    monkeypatch.setattr("velowind_appium.cleanup.ensure_logged_in_on_home", lambda *args: events.append("ensure-home"))
    monkeypatch.setattr("velowind_appium.cleanup._open_me_entry", lambda driver, text: events.append(("open", text)))
    monkeypatch.setattr(
        "velowind_appium.cleanup.cleanup_exact_visible_item",
        lambda *args, **kwargs: events.append(
            ("cleanup", kwargs["title"])
        )
        or CleanupReport("note", ["测试 - 长白山"], []),
    )
    monkeypatch.setattr("velowind_appium.cleanup.safe_back", lambda driver: events.append("back"))

    report = cleanup_published_note(object(), "测试 - 长白山", object())

    assert report == CleanupReport("note", ["测试 - 长白山"], [])
    assert events == [
        "ensure-home",
        ("open", "我的笔记"),
        ("cleanup", "测试 - 长白山"),
        "back",
    ]


def test_cleanup_exact_visible_item_returns_immediately_when_title_is_absent(monkeypatch):
    events = []
    monkeypatch.setattr(
        "velowind_appium.cleanup._tap_exact_visible_title",
        lambda driver, title: events.append(title) or False,
    )
    monkeypatch.setattr(
        "velowind_appium.cleanup.tap_first_available_text",
        lambda *args: (_ for _ in ()).throw(AssertionError("delete actions must not run")),
    )

    report = cleanup_exact_visible_item(
        object(),
        item_type="note",
        title="测试 - 长白山",
        action_texts=["删除"],
    )

    assert report == CleanupReport("note", [], [])
    assert events == ["测试 - 长白山"]


def test_cleanup_matching_visible_items_stops_when_page_is_already_at_end(monkeypatch):
    monkeypatch.setattr(
        "velowind_appium.cleanup._safe_page_source",
        lambda driver: '<App><Text text="已经到底了" /></App>',
    )
    monkeypatch.setattr(
        "velowind_appium.cleanup._scroll_page",
        lambda driver: (_ for _ in ()).throw(AssertionError("end marker must avoid scrolling")),
    )

    report = cleanup_matching_visible_items(
        object(),
        item_type="note",
        matchers=["测试 - 长白山"],
        action_texts=["删除"],
        dry_run=False,
        exact_match=True,
    )

    assert report == CleanupReport("note", [], [])


def test_cleanup_matching_visible_items_exact_match_skips_similar_title(monkeypatch):
    page_source = """
    <App>
      <Text text="测试 - 长白山旧笔记" />
      <Text text="测试 - 长白山" />
    </App>
    """
    events = []
    monkeypatch.setattr("velowind_appium.cleanup._safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(
        "velowind_appium.cleanup._delete_candidate",
        lambda driver, candidate, action_texts: events.append(candidate) or True,
    )
    monkeypatch.setattr("velowind_appium.cleanup._scroll_page", lambda driver: False)

    report = cleanup_matching_visible_items(
        object(),
        item_type="note",
        matchers=["测试 - 长白山"],
        action_texts=["删除"],
        dry_run=False,
        exact_match=True,
    )

    assert report.deleted == ["测试 - 长白山"]
    assert events == ["测试 - 长白山"]


def test_cleanup_activities_leaves_my_activity_page_after_dry_run(monkeypatch):
    events = []
    cleanup_config = type("CleanupConfig", (), {"activity_matchers": ["测试 -"]})()

    monkeypatch.setattr("velowind_appium.cleanup.ensure_logged_in_on_home", lambda *args: events.append("ensure-home"))
    monkeypatch.setattr("velowind_appium.cleanup.open_my_activity_publish_list", lambda driver: events.append("open-activities"))
    monkeypatch.setattr(
        "velowind_appium.cleanup.cleanup_matching_visible_items",
        lambda *args, **kwargs: events.append(("cleanup", kwargs["dry_run"], tuple(kwargs["required_page_texts"])))
        or CleanupReport("activity", [], ["测试 - 张家界"]),
    )
    monkeypatch.setattr("velowind_appium.cleanup.safe_back", lambda driver: events.append("back"))

    report = cleanup_activities(object(), cleanup_config, object(), dry_run=True)

    assert report == CleanupReport("activity", [], ["测试 - 张家界"])
    assert events == ["ensure-home", "open-activities", ("cleanup", True, ("通过", "上架")), "back"]


def test_cleanup_sessions_leaves_session_page_after_dry_run(monkeypatch):
    events = []
    cleanup_config = type("CleanupConfig", (), {"session_matchers": ["自动化场次"]})()

    monkeypatch.setattr("velowind_appium.cleanup.ensure_logged_in_on_home", lambda *args: events.append("ensure-home"))
    monkeypatch.setattr("velowind_appium.cleanup.open_my_activity_publish_list", lambda driver: events.append("open-activities"))
    monkeypatch.setattr("velowind_appium.cleanup.tap_text_if_present", lambda *args, **kwargs: events.append("tap-manage") or True)
    monkeypatch.setattr(
        "velowind_appium.cleanup.cleanup_matching_visible_items",
        lambda *args, **kwargs: events.append(("cleanup", kwargs["dry_run"]))
        or CleanupReport("session", [], ["自动化场次 0727"]),
    )
    monkeypatch.setattr("velowind_appium.cleanup.safe_back", lambda driver: events.append("back"))

    report = cleanup_sessions(object(), cleanup_config, object(), dry_run=True)

    assert report == CleanupReport("session", [], ["自动化场次 0727"])
    assert events == ["ensure-home", "open-activities", "tap-manage", ("cleanup", True), "back"]
