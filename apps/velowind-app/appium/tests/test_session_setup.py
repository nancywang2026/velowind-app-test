import conftest
from velowind_appium import session


def test_prepare_logged_in_session_delegates_to_me_tab_login(monkeypatch):
    driver = object()
    ios_config = object()
    calls = []

    def fake_ensure_logged_in_from_me_then_home(received_driver, received_config):
        calls.append((received_driver, received_config))
        return True

    monkeypatch.setattr(
        conftest,
        "ensure_logged_in_from_me_then_home",
        fake_ensure_logged_in_from_me_then_home,
    )

    assert conftest.prepare_logged_in_session(driver, ios_config) is True
    assert calls == [(driver, ios_config)]


def test_logged_in_session_skips_tests_without_driver_fixture(monkeypatch):
    calls = []

    class DummyRequest:
        fixturenames = []

        def getfixturevalue(self, name):
            raise AssertionError(f"should not request fixture: {name}")

    monkeypatch.setattr(conftest, "_LOGGED_IN_SESSION_READY", False)
    monkeypatch.setattr(conftest, "prepare_logged_in_session", lambda driver, ios_config: calls.append(True))

    conftest.logged_in_session.__wrapped__(DummyRequest(), object())

    assert calls == []


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
