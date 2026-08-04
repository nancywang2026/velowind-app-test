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


def test_ios_config_writes_allure_environment(monkeypatch, tmp_path):
    config = type(
        "Config",
        (),
        {
            "target": "device",
            "udid": "00008150-0006799C2693401C",
            "device_name": "Zhigang iPhone",
            "platform_version": "26.2.1",
            "server_url": "http://127.0.0.1:4723",
            "artifact_dir": tmp_path / "artifacts",
        },
    )()
    results_dir = tmp_path / "allure-results"
    artifacts = type("Artifacts", (), {"results": results_dir})()

    monkeypatch.setenv("VW_APPIUM_PLATFORM", "ios")
    monkeypatch.setattr(conftest, "load_test_config", lambda: config)
    monkeypatch.setattr(conftest, "allure_artifacts", lambda repo_root, platform: artifacts)

    loaded_config = conftest.ios_config.__wrapped__()

    assert loaded_config is config
    environment_file = results_dir / "environment.properties"
    assert environment_file.exists()
    content = environment_file.read_text(encoding="utf-8")
    assert "Platform=iOS\n" in content
    assert "Device Kind=physical\n" in content
    assert "Target=device\n" in content
    assert "Device Name=Zhigang iPhone\n" in content


def test_android_config_writes_allure_environment(monkeypatch, tmp_path):
    config = type(
        "Config",
        (),
        {
            "target": "physical",
            "udid": "YHK7EERSGAPZX87X",
            "device_name": "25060RK16C",
            "platform_version": "16",
            "server_url": "http://127.0.0.1:4724",
            "artifact_dir": tmp_path / "artifacts",
        },
    )()
    results_dir = tmp_path / "allure-results"
    artifacts = type("Artifacts", (), {"results": results_dir})()

    monkeypatch.setenv("VW_APPIUM_PLATFORM", "android")
    monkeypatch.setattr(conftest, "load_test_config", lambda: config)
    monkeypatch.setattr(conftest, "allure_artifacts", lambda repo_root, platform: artifacts)

    loaded_config = conftest.ios_config.__wrapped__()

    assert loaded_config is config
    content = (results_dir / "environment.properties").read_text(encoding="utf-8")
    assert "Platform=Android\n" in content
    assert "Device Kind=physical\n" in content
    assert "Target=physical\n" in content
    assert "Device Name=25060RK16C\n" in content


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
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "ios")

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


def test_prepare_logged_in_session_checks_me_tab_first_on_android(monkeypatch):
    driver = object()
    android_config = object()
    calls = []
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "android")

    def fake_ensure_logged_in_from_me_then_home(received_driver, received_config):
        calls.append((received_driver, received_config))
        return True

    monkeypatch.setattr(
        conftest,
        "ensure_logged_in_from_me_then_home",
        fake_ensure_logged_in_from_me_then_home,
    )

    assert conftest.prepare_logged_in_session(driver, android_config) is True
    assert calls == [(driver, android_config)]


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


def test_logged_in_session_can_skip_home_preparation_with_marker(monkeypatch):
    calls = []

    class DummyNode:
        @staticmethod
        def get_closest_marker(name):
            return object() if name == "skip_home_session" else None

    class DummyRequest:
        fixturenames = ["driver"]
        node = DummyNode()

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


def test_home_and_publish_entry_reject_profile_content_pages():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="个人资料" visible="true" />
      <XCUIElementTypeStaticText name="昵称" visible="true" />
      <XCUIElementTypeStaticText name="手机号" visible="true" />
      <XCUIElementTypeStaticText name="实名认证状态" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_interest_preferences_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="兴趣偏好" visible="true" />
      <XCUIElementTypeStaticText name="骑行" visible="true" />
      <XCUIElementTypeStaticText name="徒步" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_my_coupons_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="我的卡券" visible="true" />
      <XCUIElementTypeStaticText name="暂无卡券" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_settings_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="设置" visible="true" />
      <XCUIElementTypeStaticText name="语言 · 简体中文" visible="true" />
      <XCUIElementTypeStaticText name="账号与安全" visible="true" />
      <XCUIElementTypeStaticText name="退出登录" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_account_security_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="账号与安全" visible="true" />
      <XCUIElementTypeStaticText name="绑定手机号" visible="true" />
      <XCUIElementTypeStaticText name="设置/修改密码" visible="true" />
      <XCUIElementTypeStaticText name="账号注销" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_leader_application_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="成为领队" visible="true" />
      <XCUIElementTypeStaticText name="寻风集领队，等你加入" visible="true" />
      <XCUIElementTypeStaticText name="温馨提示" visible="true" />
      <XCUIElementTypeStaticText name="申请状态" visible="true" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_and_publish_entry_reject_system_message_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="全国 推荐 笔记 活动 消息 我的" visible="false" />
      <XCUIElementTypeStaticText name="系统消息" visible="true" />
      <XCUIElementTypeStaticText name="活动通知" visible="true" />
      <XCUIElementTypeStaticText name="07-31 17:45" visible="true" />
      <XCUIElementTypeStaticText name="有新的活动报名" visible="true" />
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


def test_home_and_publish_entry_reject_rental_page_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="活动" />
      <XCUIElementTypeStaticText name="消息" />
      <XCUIElementTypeStaticText name="我的" />
      <XCUIElementTypeOther name="rent-page-shell" />
      <XCUIElementTypeStaticText name="租车" />
      <XCUIElementTypeStaticText name="立即选车" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False
    assert session._publish_entry_ready(driver) is False


def test_home_or_login_visible_rejects_rental_date_picker_over_note_home():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="全国 推荐 骑行 徒步 笔记 活动 消息 我的" />
      <XCUIElementTypeOther name="租车 用车时间 服务门店 立即选车 选择取还车日期 取消 确定" />
    </AppiumAUT>
    """

    class FakeDriver:
        def __init__(self, source):
            self.page_source = source

    driver = FakeDriver(page_source)
    assert session._home_visible(driver) is False
    assert session._home_or_login_visible(driver) is False


def test_home_and_publish_entry_reject_note_search_overlay():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="首页 活动 消息 我的" visible="false" />
      <XCUIElementTypeTextField
        value="骑行"
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
    assert ("tap-tab", "bottom-nav-home", "笔记") in events


def test_ensure_logged_in_from_me_then_home_waits_for_delayed_android_login(monkeypatch):
    events = []
    page_sources = iter(
        [
            "首页 推荐 活动 消息 我的",
            "首页 推荐 活动 消息 我的",
            "再逛逛 手机号登录 请输入手机号 密码登录 验证并登录",
            "首页 推荐 活动 消息 我的",
        ]
    )

    class FakeDriver:
        capabilities = {"platformName": "Android"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: events.append(("tap-tab", accessibility_id, text)) or True,
    )
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: next(page_sources))
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: events.append("login") or True)
    monkeypatch.setattr(session, "_home_visible", lambda driver: True)

    assert session.ensure_logged_in_from_me_then_home(FakeDriver(), object()) is True
    assert "login" in events


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


def test_ensure_logged_in_from_me_then_home_recovers_android_search_page_before_opening_me(monkeypatch):
    state = {"page": "search"}
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: False)
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or True)

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        events.append(("tap-tab", accessibility_id, text, state["page"]))
        if accessibility_id == "bottom-nav-me" and state["page"] == "home":
            state["page"] = "me"
            return True
        if accessibility_id == "bottom-nav-home" and state["page"] == "me":
            state["page"] = "home"
            return True
        return False

    def fake_android_adb_back(driver):
        events.append("android-adb-back")
        if events.count("android-adb-back") >= 2:
            state["page"] = "home"
        return True

    monkeypatch.setattr(session, "tap_accessibility_id_or_text_if_present", fake_tap_tab)
    monkeypatch.setattr(session, "_android_adb_back", fake_android_adb_back)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or False)

    assert session.ensure_logged_in_from_me_then_home(FakeDriver(), object()) is True
    assert events.count("android-adb-back") == 2
    assert ("tap-tab", "bottom-nav-me", "我的", "home") in events
    assert ("tap-tab", "bottom-nav-home", "笔记", "me") in events


def test_ensure_logged_in_from_me_then_home_uses_home_recovery_when_android_keyboard_blocks_tabs(monkeypatch):
    state = {"page": "activity-search-keyboard"}
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "_login_required_after_short_wait", lambda driver: False)
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or True)

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        events.append(("tap-tab", accessibility_id, text, state["page"]))
        if accessibility_id == "bottom-nav-me" and state["page"] == "home":
            state["page"] = "me"
            return True
        if accessibility_id == "bottom-nav-home" and state["page"] == "me":
            state["page"] = "home"
            return True
        return False

    def fake_android_adb_back(driver):
        events.append(("android-adb-back", state["page"]))
        return True

    def fake_ensure_logged_in_on_home(driver, config):
        events.append("recover-home")
        state["page"] = "home"
        return False

    monkeypatch.setattr(session, "tap_accessibility_id_or_text_if_present", fake_tap_tab)
    monkeypatch.setattr(session, "_android_adb_back", fake_android_adb_back)
    def fake_tap_home_tab(driver, timeout=3):
        events.append(("tap-home", state["page"]))
        if state["page"] == "me":
            state["page"] = "home"
            return True
        return False

    monkeypatch.setattr(session, "_tap_home_tab", fake_tap_home_tab)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or False)
    monkeypatch.setattr(session, "ensure_logged_in_on_home", fake_ensure_logged_in_on_home)

    assert session.ensure_logged_in_from_me_then_home(FakeDriver(), object()) is True
    assert "recover-home" in events
    assert ("tap-tab", "bottom-nav-me", "我的", "home") in events
    assert ("tap-home", "me") in events
    assert state["page"] == "home"


def test_ensure_logged_in_from_me_then_home_recovers_android_system_message_page(monkeypatch):
    state = {"page": "系统消息 内容通知 内容审核已通过"}
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "ensure_logged_in_if_needed", lambda driver, config: False)
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or state["page"] == "home")

    def fake_tap_tab(driver, accessibility_id, text, timeout=3):
        events.append(("tap-tab", accessibility_id, text, state["page"]))
        if accessibility_id == "bottom-nav-home" and "消息" in state["page"]:
            state["page"] = "home"
            return True
        if accessibility_id == "bottom-nav-me" and state["page"] == "home":
            state["page"] = "me"
            return True
        return False

    def fake_android_adb_back(driver):
        events.append("android-adb-back")
        state["page"] = "消息 系统通知 系统消息 内容通知 笔记 活动 我的"
        return True

    monkeypatch.setattr(session, "tap_accessibility_id_or_text_if_present", fake_tap_tab)
    monkeypatch.setattr(session, "_android_adb_back", fake_android_adb_back)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or False)

    assert session.ensure_logged_in_from_me_then_home(FakeDriver(), object()) is True
    assert ("tap-tab", "bottom-nav-home", "笔记", "消息 系统通知 系统消息 内容通知 笔记 活动 我的") in events
    assert events[-1] == "wait-home"


def test_ensure_logged_in_from_me_then_home_falls_back_when_final_home_wait_times_out(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: "消息 系统通知 系统消息 活动 消息 我的")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(session, "_login_required_after_short_wait", lambda driver: False)
    monkeypatch.setattr(session, "_tap_home_tab", lambda driver, timeout=8: events.append(("tap-home", timeout)) or True)
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or (_ for _ in ()).throw(AssertionError("still on messages")))
    monkeypatch.setattr(session, "ensure_logged_in_on_home", lambda driver, config: events.append("fallback-home") or False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: events.append(("tap-tab", accessibility_id, text)) or accessibility_id == "bottom-nav-me",
    )

    assert session.ensure_logged_in_from_me_then_home(FakeDriver(), object()) is True
    assert events[-2:] == ["wait-home", "fallback-home"]


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


def test_ensure_logged_in_on_home_with_step_recovers_profile_page_before_waiting(monkeypatch):
    state = {"page": "profile"}
    events = []

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "_home_or_login_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or state.update(page="home"))

    def fake_wait_for_home_feed(driver, timeout=20):
        assert state["page"] == "home", "waited for home before recovering from the profile page"
        events.append("wait-home")
        return True

    def fake_step(label, action):
        events.append(("step", label))
        return action()

    monkeypatch.setattr(session, "wait_for_home_feed", fake_wait_for_home_feed)

    assert session.ensure_logged_in_on_home(object(), object(), step=fake_step) is False
    assert events[0] == ("step", "recover-home-session")


def test_ensure_logged_in_on_home_relaunches_android_app_from_launcher(monkeypatch):
    state = {"page": "com.google.android.apps.nexuslauncher 寻风集"}
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
    monkeypatch.setattr(session, "_android_adb_back", lambda driver: events.append("adb-back") or False)
    monkeypatch.setattr(session, "safe_back", lambda driver: events.append("safe-back") or False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: events.append(("tap", accessibility_id, text)) or state.update(page="home") or True,
    )
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: events.append("wait-home") or True)

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert events[0] == ("tap", "寻风集", "寻风集")
    assert state["page"] == "home"


def test_home_or_login_visible_allows_message_tab_with_system_message_text(monkeypatch):
    page_source = "消息 系统通知 系统消息 笔记 活动 我的"

    monkeypatch.setattr(session, "_safe_page_source", lambda driver: page_source)

    assert session._home_or_login_visible(object()) is True


def test_home_or_login_visible_rejects_system_message_detail_overlay(monkeypatch):
    page_source = "全国 推荐 骑行 徒步 笔记 活动 消息 我的 系统消息 内容通知 内容审核已通过"

    monkeypatch.setattr(session, "_safe_page_source", lambda driver: page_source)

    assert session._home_or_login_visible(object()) is False


def test_ensure_logged_in_on_home_uses_coordinate_home_tab_fallback(monkeypatch):
    state = {"page": "消息 系统通知 系统消息 笔记 活动 我的"}
    events = []

    class FakeDriver:
        @staticmethod
        def get_window_rect():
            return {"width": 1280, "height": 2568}

        @staticmethod
        def execute_script(script, payload):
            events.append((script, payload))
            state["page"] = "home"

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: state["page"] == "home")

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert events == [("mobile: tap", {"x": 153, "y": 2311})]


def test_ensure_logged_in_on_home_taps_android_home_text_when_generic_lookup_misses(monkeypatch):
    state = {"page": "消息 系统通知 系统消息 笔记 活动 我的"}
    events = []

    class FakeElement:
        @staticmethod
        def get_attribute(name):
            return "[79,2568][178,2640]" if name == "bounds" else ""

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        @staticmethod
        def find_element(by, xpath):
            events.append(("find", by, xpath))
            if '@text="笔记"' in xpath:
                return FakeElement()
            raise AssertionError(f"unexpected xpath: {xpath}")

        @staticmethod
        def execute_script(script, payload):
            events.append((script, payload))
            state["page"] = "home"

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )
    monkeypatch.setattr(session, "_tap_home_tab_by_coordinate", lambda driver: events.append("coordinate-home") or False)
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: state["page"] == "home")
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda command, **kwargs: events.append(("adb", command)) or state.update(page="home"),
    )

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert ("mobile: tap", {"x": 128, "y": 2604}) in events
    assert ("adb", ["adb", "-s", "YHK7EERSGAPZX87X", "shell", "input", "tap", "128", "2604"]) in events
    assert "coordinate-home" not in events


def test_ensure_logged_in_on_home_uses_low_android_home_tab_coordinate_when_text_lookup_misses(monkeypatch):
    state = {"page": "消息 系统通知 系统消息 笔记 活动 我的"}
    events = []

    class FakeDriver:
        capabilities = {"platformName": "Android", "appium:udid": "YHK7EERSGAPZX87X"}

        @staticmethod
        def find_element(by, xpath):
            raise session.NoSuchElementException()

        @staticmethod
        def get_window_rect():
            return {"width": 1280, "height": 2772}

        @staticmethod
        def execute_script(script, payload):
            events.append((script, payload))
            state["page"] = "home"

    monkeypatch.setattr(session, "dismiss_common_system_alerts", lambda driver: None)
    monkeypatch.setattr(session, "tap_text_if_present", lambda driver, text, timeout=1: False)
    monkeypatch.setattr(session, "_safe_page_source", lambda driver: state["page"])
    monkeypatch.setattr(session, "_home_visible", lambda driver: state["page"] == "home")
    monkeypatch.setattr(session, "login_required_from_page_source", lambda page_source: False)
    monkeypatch.setattr(
        session,
        "tap_accessibility_id_or_text_if_present",
        lambda driver, accessibility_id, text, timeout=3: False,
    )
    monkeypatch.setattr(session, "_tap_home_tab_by_coordinate", lambda driver: events.append("legacy-coordinate-home") or False)
    monkeypatch.setattr(session, "wait_for_home_feed", lambda driver, timeout=20: state["page"] == "home")
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda command, **kwargs: events.append(("adb", command)) or state.update(page="home"),
    )

    assert session.ensure_logged_in_on_home(FakeDriver(), object()) is False
    assert ("mobile: tap", {"x": 128, "y": 2605}) in events
    assert ("adb", ["adb", "-s", "YHK7EERSGAPZX87X", "shell", "input", "tap", "128", "2605"]) in events
    assert "legacy-coordinate-home" not in events


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
