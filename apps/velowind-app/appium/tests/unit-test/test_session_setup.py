import conftest
import pytest
from velowind_appium import session
import itertools
from pathlib import Path


def test_load_test_config_uses_android_config_when_platform_is_android(monkeypatch):
    expected = object()
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "android")
    monkeypatch.setattr(conftest, "load_android_config", lambda: expected)

    assert conftest.load_test_config() is expected


def test_create_test_driver_uses_android_driver_when_platform_is_android(monkeypatch):
    config = object()
    expected = object()
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "android")
    monkeypatch.setattr(conftest, "create_android_driver", lambda received: expected if received is config else None)

    assert conftest.create_test_driver(config) is expected


def test_prepare_logged_in_session_delegates_to_recoverable_home_setup(monkeypatch):
    driver = object()
    ios_config = object()
    calls = []

    def fake_ensure_logged_in_on_home(received_driver, received_config):
        calls.append((received_driver, received_config))
        return True

    monkeypatch.setattr(
        conftest,
        "ensure_logged_in_on_home",
        fake_ensure_logged_in_on_home,
    )

    assert conftest.prepare_logged_in_session(driver, ios_config) is True
    assert calls == [(driver, ios_config)]


def test_logged_in_session_skips_tests_without_driver_fixture(monkeypatch):
    calls = []

    class DummyRequest:
        fixturenames = []

        def getfixturevalue(self, name):
            raise AssertionError(f"should not request fixture: {name}")

    monkeypatch.setattr(conftest, "prepare_logged_in_session", lambda driver, ios_config: calls.append(True))

    fixture = conftest.logged_in_session.__wrapped__(DummyRequest(), object())
    next(fixture)
    with pytest.raises(StopIteration):
        next(fixture)

    assert calls == []


def test_logged_in_session_prepares_before_and_after_every_driver_case(monkeypatch):
    driver = object()
    ios_config = object()
    calls = []

    class DummyRequest:
        fixturenames = ["driver"]

        def getfixturevalue(self, name):
            assert name == "driver"
            return driver

    monkeypatch.setattr(
        conftest,
        "prepare_logged_in_session",
        lambda received_driver, received_config: calls.append((received_driver, received_config)),
    )

    for _ in range(2):
        fixture = conftest.logged_in_session.__wrapped__(DummyRequest(), ios_config)
        next(fixture)
        with pytest.raises(StopIteration):
            next(fixture)

    assert calls == [(driver, ios_config)] * 4


def test_capture_each_step_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VW_APPIUM_CAPTURE_EACH_STEP", raising=False)

    assert conftest.should_capture_each_step() is False


def test_capture_each_step_can_be_enabled(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CAPTURE_EACH_STEP", "true")

    assert conftest.should_capture_each_step() is True


def test_dismiss_common_system_alerts_uses_short_optional_probes(monkeypatch):
    calls = []

    monkeypatch.setattr(
        session,
        "tap_text_if_present",
        lambda driver, text, timeout=1: calls.append((text, timeout)) or False,
    )

    session.dismiss_common_system_alerts(object())

    assert calls == [(text, 0.2) for text in session.COMMON_ALERT_TEXTS]


def test_dismiss_common_system_alerts_skips_step_when_alert_is_not_found(monkeypatch):
    step_calls = []

    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)

    session.dismiss_common_system_alerts(
        object(),
        step=lambda label, action: step_calls.append(label) or action(),
    )

    assert step_calls == []


def test_dismiss_common_system_alerts_records_step_only_for_matched_alert(monkeypatch):
    step_calls = []

    monkeypatch.setattr(
        session,
        "tap_text_if_present",
        lambda driver, text, timeout=1: text == "好",
    )

    session.dismiss_common_system_alerts(
        object(),
        step=lambda label, action: step_calls.append(label) or action(),
    )

    assert step_calls == ["dismiss-alert-好"]


def test_pytest_runtest_makereport_captures_final_page_for_passed_test(monkeypatch):
    captured = []

    class DummyOutcome:
        @staticmethod
        def get_result():
            class Report:
                when = "call"
                passed = True

            return Report()

    class DummyItem:
        funcargs = {
            "driver": object(),
            "ios_config": type("Config", (), {"artifact_dir": Path(".tmp/appium-ios")})(),
        }
        name = "test_demo"

    class StepContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(conftest.allure, "step", lambda title: captured.append(("step", title)) or StepContext())
    monkeypatch.setattr(
        conftest,
        "capture_and_attach_page",
        lambda driver, artifact_dir, label: captured.append(("capture", label, artifact_dir)),
    )

    hook = conftest.pytest_runtest_makereport(DummyItem(), None)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(DummyOutcome())

    assert captured == [
        ("step", "final-page"),
        ("capture", "test_demo-final-page", Path(".tmp/appium-ios")),
    ]


def test_home_visible_rejects_publish_form_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="全国" />
      <XCUIElementTypeStaticText name="发布活动" />
      <XCUIElementTypeStaticText name="提交审核" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    assert session._home_visible(FakeDriver(page_source)) is False


def test_home_visible_rejects_message_detail_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="全国" />
      <XCUIElementTypeStaticText name="写留言" />
      <XCUIElementTypeOther name="post-detail-banner-pager" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    assert session._home_visible(FakeDriver(page_source)) is False


def test_home_visible_rejects_activity_detail_preview_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="活动" />
      <XCUIElementTypeStaticText name="消息" />
      <XCUIElementTypeStaticText name="我的" />
      <XCUIElementTypeOther name="activity-route-detail-v3-hero-carousel" />
      <XCUIElementTypeStaticText name="活动详情" />
      <XCUIElementTypeStaticText name="页面预览提示" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    assert session._home_visible(FakeDriver(page_source)) is False
    assert session._home_or_login_visible(FakeDriver(page_source)) is False


def test_home_and_publish_entry_reject_my_activities_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="活动" />
      <XCUIElementTypeStaticText name="消息" />
      <XCUIElementTypeStaticText name="我的" />
      <XCUIElementTypeStaticText name="我的活动" />
      <XCUIElementTypeStaticText name="报名" />
      <XCUIElementTypeStaticText name="点赞" />
      <XCUIElementTypeStaticText name="收藏" />
      <XCUIElementTypeStaticText name="发布" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_my_notes_overlay():
    page_source = """
    <AppiumAUT>
      <android.widget.TextView text="我的笔记" />
      <android.widget.TextView text="长白山真的有种让人瞬间安静下来的魔力" />
    </AppiumAUT>
    """

    class FakeDriver:
        pass

    driver = FakeDriver()
    driver.page_source = page_source

    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_note_search_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeTextField
        value="骑行的"
        placeholderValue="请输入内容"
        visible="true"
      />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_android_note_search_overlay():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="首页" displayed="true" />
      <android.widget.TextView text="推荐" displayed="true" />
      <android.widget.EditText text="骑行" hint="请输入内容" displayed="true" />
      <android.widget.FrameLayout
        resource-id="post-home-feed-category-pager"
        displayed="true"
      />
    </hierarchy>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_visible_rejects_login_sheet_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="全国" />
      <XCUIElementTypeStaticText name="手机号登录" />
      <XCUIElementTypeTextField value="请输入手机号" />
      <XCUIElementTypeStaticText name="验证并登录" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    assert session._home_visible(FakeDriver(page_source)) is False


def test_ensure_logged_in_from_me_then_home_opens_me_before_login(monkeypatch):
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: events.append("dismiss-alerts"))
    monkeypatch.setattr(
        session,
        "tap_text_if_present",
        lambda driver, text, timeout=1: events.append(("tap-text", text)) or False,
    )

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        events.append(("tap-tab", accessibility_id, text))
        return True

    monkeypatch.setattr(session, "tap_accessibility_id_or_text_if_present", fake_tap_tab)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: "手机号登录 请输入手机号 登录")
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: events.append("login") or True)
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or True)
    monkeypatch.setattr(session, "_home_visible", lambda driver: True)

    assert session.ensure_logged_in_from_me_then_home(object(), object()) is True
    assert events[:4] == [
        "dismiss-alerts",
        ("tap-text", "同意并继续"),
        ("tap-text", "同意"),
        ("tap-tab", "bottom-nav-me", "我的"),
    ]
    assert "login" in events
    assert ("tap-tab", "bottom-nav-home", "首页") in events


def test_ensure_logged_in_from_me_then_home_can_login_when_me_tab_is_not_tappable(monkeypatch):
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: events.append("dismiss-alerts"))
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False if accessibility_id == "bottom-nav-me" else True,
    )
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: "密码登录 请输入手机号和密码完成登录 登录")
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: events.append("login") or True)
    monkeypatch.setattr(session, "_home_visible", lambda driver: True)

    assert session.ensure_logged_in_from_me_then_home(object(), object()) is True
    assert "login" in events


def test_ensure_logged_in_on_home_recovers_detail_page_before_waiting(monkeypatch):
    state = {"page": "detail"}
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )

    def fake_back(driver):
        events.append("back")
        state["page"] = "home"
        return True

    def fake_wait_for_home_feed(driver, timeout=20):
        assert state["page"] == "home", "waited for home before recovering from the detail page"
        events.append("wait-home")
        return True

    monkeypatch.setattr(session, "safe_back", fake_back)
    monkeypatch.setattr(session, "wait_for_home_feed", fake_wait_for_home_feed)

    assert session.ensure_logged_in_on_home(object(), object()) is False
    assert events[0] == "back"


def test_ensure_logged_in_on_home_uses_android_adb_back_for_blocking_detail(monkeypatch):
    state = {"page": "detail"}
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "emulator-5554"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "_tap_top_back_by_coordinate", lambda driver: events.append("top-back") or False)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )

    def fake_android_adb_back(driver):
        events.append("android-adb-back")
        state["page"] = "home"
        return True

    monkeypatch.setattr(session, "_android_adb_back", fake_android_adb_back)
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or True)

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert "android-adb-back" in events
    assert "wait-home" not in events


def test_ensure_logged_in_on_home_unwinds_nested_blocking_pages(monkeypatch):
    pages = ["activity-detail", "my-activities", "profile", "home"]
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: pages[0])
    monkeypatch.setattr(session, "_home_visible", lambda driver: pages[0] == "home")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: pages[0] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )

    def fake_back(driver):
        events.append(("back", pages[0]))
        if len(pages) > 1:
            pages.pop(0)
        return True

    monkeypatch.setattr(session, "safe_back", fake_back)
    monkeypatch.setattr(
        session,
        "wait_for_home_feed",
        lambda driver, timeout=20: True if pages[0] == "home" else (_ for _ in ()).throw(AssertionError("not home")),
    )

    assert session.ensure_logged_in_on_home(object(), object()) is False
    assert pages[0] == "home"
    assert len(events) == 3


def test_ensure_logged_in_on_home_taps_unlabeled_top_back_on_my_activities(monkeypatch):
    state = {"page": "my-activities"}
    taps = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "safe_back", lambda driver: None)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: True)

    class FakeDriver:
        @staticmethod
        def get_window_rect():
            return {"width": 402, "height": 874}

        @staticmethod
        def execute_script(script, payload):
            taps.append((script, payload))
            state["page"] = "home"

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert taps == [("mobile: tap", {"x": 20, "y": 87})]


def test_ensure_logged_in_on_home_discards_unpublished_note_draft(monkeypatch):
    state = {"page": "publisher"}
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )

    def fake_top_back(driver):
        events.append("top-back")
        state["page"] = "是否保存草稿 不保存 保存草稿"
        return True

    def fake_tap_text(driver, text, timeout=1):
        if text == "不保存" and "是否保存草稿" in state["page"]:
            events.append("discard")
            state["page"] = "home"
            return True
        return False

    monkeypatch.setattr(session, "_tap_top_back_by_coordinate", fake_top_back)
    monkeypatch.setattr(session, "tap_text_if_present", fake_tap_text)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back"))
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: True)

    assert session.ensure_logged_in_on_home(object(), object()) is False
    assert events == ["top-back", "discard"]


def test_ensure_logged_in_for_publish_entry_returns_immediately_when_publish_entry_ready(monkeypatch):
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: events.append("dismiss-alerts"))
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_publish_entry_ready", lambda driver: True)

    assert session.ensure_logged_in_for_publish_entry(object(), object()) is False
    assert events == ["dismiss-alerts"]


def test_ensure_logged_in_for_publish_entry_logs_in_and_recovers(monkeypatch):
    events = []
    state = {"page": "login"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: events.append("dismiss-alerts"))
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page: page == "login")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: True)
    monkeypatch.setattr(session, "_publish_entry_ready", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: events.append("login") or state.update(page="home") or True)
    monkeypatch.setattr(session, "_tap_home_tab_by_coordinate", lambda driver: events.append("tap-home-fast") or True)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("back"))
    monkeypatch.setattr(session.time, "monotonic", itertools.count().__next__)
    monkeypatch.setattr(session.time, "sleep", lambda seconds: None)

    assert session.ensure_logged_in_for_publish_entry(object(), object()) is True
    assert "login" in events
    assert "tap-home-fast" not in events


def test_ensure_logged_in_for_publish_entry_unwinds_my_notes_detail(monkeypatch):
    pages = ["my-note-detail", "my-notes", "home"]
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: events.append("dismiss-alerts"))
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: pages[0])
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page: False)
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: pages[0] == "home")
    monkeypatch.setattr(session, "_publish_entry_ready", lambda driver: pages[0] == "home")
    monkeypatch.setattr(session, "_tap_home_tab_by_coordinate", lambda driver: events.append("tap-home-fast") or True)

    def fake_top_back(driver):
        events.append(("top-back", pages[0]))
        if len(pages) > 1:
            pages.pop(0)
        return True

    def fake_back(driver):
        events.append(("back", pages[0]))
        if len(pages) > 1:
            pages.pop(0)
        return True

    monkeypatch.setattr(session, "_tap_top_back_by_coordinate", fake_top_back)
    monkeypatch.setattr(session, "safe_back", fake_back)
    monkeypatch.setattr(session.time, "monotonic", itertools.count().__next__)
    monkeypatch.setattr(session.time, "sleep", lambda seconds: None)

    assert session.ensure_logged_in_for_publish_entry(object(), object()) is False
    assert pages[0] == "home"
    assert ("top-back", "my-note-detail") in events
