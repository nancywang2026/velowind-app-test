from selenium.common.exceptions import NoSuchElementException

from velowind_appium import auth
from velowind_appium.auth import login_required_from_page_source


def test_login_required_from_page_source_detects_phone_login_screen():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="手机号登录" />
      <XCUIElementTypeStaticText name="请输入手机号" />
      <XCUIElementTypeStaticText name="验证并登录" />
    </AppiumAUT>
    """

    assert login_required_from_page_source(page_source) is True


def test_login_required_from_page_source_ignores_content_page():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="首页" />
      <XCUIElementTypeStaticText name="推荐" />
    </AppiumAUT>
    """

    assert login_required_from_page_source(page_source) is False


def test_login_required_from_page_source_detects_password_login_screen():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="密码登录" />
      <XCUIElementTypeStaticText name="请输入手机号和密码完成登录" />
      <XCUIElementTypeStaticText name="登录" />
    </AppiumAUT>
    """

    assert login_required_from_page_source(page_source) is True


def test_open_password_login_form_taps_agreement_after_switch_attempt(monkeypatch):
    events = []

    class FakeElement:
        def click(self):
            events.append("click-password-login")

    class FakeDriver:
        def find_element(self, by, value):
            if "密码登录" in value:
                return FakeElement()
            raise NoSuchElementException()

    visible_checks = iter([False, True])

    monkeypatch.setattr(auth, "_has_password_input", lambda driver: False)
    monkeypatch.setattr(auth, "_safe_page_source", lambda driver: "手机号登录")
    monkeypatch.setattr(
        auth,
        "_password_form_visible",
        lambda driver, baseline: events.append("check-password-form") or next(visible_checks),
    )
    monkeypatch.setattr(auth, "_tap_agreement", lambda driver: events.append("tap-agreement"))
    monkeypatch.setattr(auth.time, "sleep", lambda seconds: None)

    auth._open_password_login_form(FakeDriver())

    assert events[:3] == [
        "click-password-login",
        "tap-agreement",
        "check-password-form",
    ]


def test_tap_agreement_targets_checkbox_before_label():
    taps = []
    attempted_xpaths = []

    class FakeElement:
        def __init__(self, rect):
            self.rect = rect

    class FakeDriver:
        def find_element(self, by, value):
            attempted_xpaths.append(value)
            if attempted_xpaths == [
                '//XCUIElementTypeOther[@name="我已阅读并同意《寻风集用户协议》《隐私政策》"]/XCUIElementTypeOther[1]'
            ]:
                return FakeElement({"x": 46, "y": 450, "width": 20, "height": 20})
            raise NoSuchElementException()

        def execute_script(self, script, payload):
            taps.append((script, payload))

    auth._tap_agreement(FakeDriver())

    assert taps == [("mobile: tap", {"x": 56.0, "y": 460.0})]


def test_perform_password_login_uses_password_form_then_saves_password(monkeypatch):
    events = []

    class FakePhoneField:
        def click(self):
            events.append("click-phone")

        def clear(self):
            events.append("clear-phone")

        def send_keys(self, value):
            events.append(("send-phone", value))

    class FakePasswordField:
        def click(self):
            events.append("click-password")

        def clear(self):
            events.append("clear-password")

        def send_keys(self, value):
            events.append(("send-password", value))

    monkeypatch.setattr(auth, "_dismiss_login_agreement_sheet", lambda driver: events.append("dismiss-sheet"))
    monkeypatch.setattr(auth, "_find_phone_input", lambda driver: FakePhoneField())
    monkeypatch.setattr(auth, "_tap_agreement", lambda driver: events.append("tap-agreement"))
    monkeypatch.setattr(auth, "_open_password_login_form", lambda driver: events.append("open-password-form"))
    monkeypatch.setattr(auth, "_find_password_input", lambda driver: FakePasswordField())
    monkeypatch.setattr(auth, "_tap_login_submit", lambda driver: True)
    monkeypatch.setattr(auth, "_save_password_if_prompted", lambda driver: events.append("save-password"))
    monkeypatch.setattr(auth, "_safe_page_source", lambda driver: "")
    monkeypatch.setattr(auth.time, "monotonic", lambda: 0)
    monkeypatch.setattr(auth.time, "sleep", lambda seconds: None)

    auth._perform_password_login(object(), "13300000000", "secret")

    assert events[:10] == [
        "dismiss-sheet",
        "open-password-form",
        "click-phone",
        "clear-phone",
        ("send-phone", "13300000000"),
        "click-password",
        "clear-password",
        ("send-password", "secret"),
        "tap-agreement",
        "save-password",
    ]
