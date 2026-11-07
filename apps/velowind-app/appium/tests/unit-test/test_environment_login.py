from dataclasses import dataclass
import json
from types import SimpleNamespace
import urllib.request

import pytest
import yaml

from velowind_appium import environment_login as env
from velowind_appium import auth, cleanup, note_api_cleanup as api


@dataclass(frozen=True)
class Config:
    login_username: str = "old-account"
    login_password: str = "old-password"


@pytest.fixture
def candidates():
    return [env.EnvironmentAccount("test", "https://test.example/api/v1/mobile", "phone", "test-password"),
            env.EnvironmentAccount("prod", "https://prod.example/api/v1/mobile", "phone", "prod-password")]


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("VW_API_ENV", raising=False)
    entries = {}
    for name in ("test", "prod"):
        p = tmp_path / f"{name}.yaml"
        p.write_text(yaml.safe_dump({"login": {"username": "phone", "password": f"{name}-password"}}))
        entries[name] = {"api_base_url": f"https://{name}.example", "config_file": p.name}
    p = tmp_path / "environments.yaml"
    p.write_text(yaml.safe_dump({"environments": entries}, sort_keys=False))
    monkeypatch.setenv("VW_APPIUM_ENVIRONMENT_ACCOUNTS", str(p))
    return p


def test_load_resolves_relative_credential_paths_without_revealing_secrets(manifest):
    accounts = env.load_environment_accounts()
    assert {a.environment for a in accounts} == {"test", "prod"}
    assert all(a.api_base_url.endswith("/api/v1/mobile") for a in accounts)
    assert "password" not in repr(accounts) and "phone" not in repr(accounts)


@pytest.mark.parametrize("failure", ["missing-file", "missing-login", "same-credentials", "same-url", "http-url", "one-environment"])
def test_invalid_manifest_fails_before_device_interaction(manifest, failure):
    d = yaml.safe_load(manifest.read_text())
    entries = d["environments"]
    if failure == "missing-file":
        entries["test"]["config_file"] = "missing.yaml"
    elif failure == "missing-login":
        (manifest.parent / "test.yaml").write_text("login: {}")
    elif failure == "same-credentials":
        (manifest.parent / "test.yaml").write_text((manifest.parent / "prod.yaml").read_text())
    elif failure == "same-url":
        entries["test"]["api_base_url"] = entries["prod"]["api_base_url"]
    elif failure == "http-url":
        entries["test"]["api_base_url"] = "http://test.example"
    else:
        del entries["prod"]
    manifest.write_text(yaml.safe_dump(d))
    with pytest.raises(ValueError):
        env.load_environment_accounts()


def test_disabled_detection_preserves_existing_behavior(monkeypatch):
    monkeypatch.delenv("VW_APPIUM_ENVIRONMENT_ACCOUNTS", raising=False)
    monkeypatch.delenv("VW_API_ENV", raising=False)
    monkeypatch.setattr(env, "_read_yaml_config", lambda: {})
    assert env.detect_app_environment(object(), Config()) is None


@pytest.mark.parametrize("preferred", ["test", "prod"])
@pytest.mark.parametrize("preferred_rejected", [False, True])
def test_environment_preference_controls_real_attempt_order_with_fallback(manifest, monkeypatch, preferred, preferred_rejected):
    monkeypatch.setenv("VW_API_ENV", preferred)
    attempts = []
    driver = SimpleNamespace(page_source="<root/>")
    monkeypatch.setattr(env, "_open_fresh_login", lambda *a: None)
    monkeypatch.setattr(env, "_tap", lambda *a: None)
    monkeypatch.setattr(env, "_authenticated_me_visible", lambda *a: True)
    monkeypatch.setattr(env, "_wait", lambda condition, timeout=12: condition())
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **kw: pytest.fail("App environment detection must not request any API"))
    monkeypatch.setattr(auth, "_tap_home_tab", lambda *a, **kw: None)
    def login(driver, username, password, *, resubmit):
        candidate = password.removesuffix("-password")
        attempts.append(candidate)
        if preferred_rejected and candidate == preferred:
            raise auth.LoginRejected("rejected")
    monkeypatch.setattr(auth, "_perform_password_login", login)
    selected = env.detect_app_environment(driver, Config())
    other = "test" if preferred == "prod" else "prod"
    assert attempts == ([preferred, other] if preferred_rejected else [preferred])
    assert selected.environment == (other if preferred_rejected else preferred)


def test_vw_api_env_alone_enables_existing_default_candidate_manifest(manifest, monkeypatch):
    monkeypatch.delenv("VW_APPIUM_ENVIRONMENT_ACCOUNTS", raising=False)
    monkeypatch.setenv("VW_API_ENV", "prod")
    monkeypatch.setattr(env, "_read_yaml_config", lambda: {})
    monkeypatch.setattr(env, "DEFAULT_ENVIRONMENT_ACCOUNTS", manifest)
    assert [a.environment for a in env.load_environment_accounts()] == ["prod", "test"]


@pytest.mark.parametrize("preferred", ["", "dev", "uat"])
def test_missing_or_invalid_preferred_candidate_fails_before_login(manifest, monkeypatch, preferred):
    monkeypatch.setenv("VW_API_ENV", preferred)
    with pytest.raises(ValueError, match="VW_API_ENV"):
        env.load_environment_accounts()


def test_no_preference_keeps_manifest_order(manifest):
    assert [a.environment for a in env.load_environment_accounts()] == ["test", "prod"]


@pytest.fixture
def detection(monkeypatch, candidates):
    events = []
    driver = SimpleNamespace(page_source="<root/>")
    monkeypatch.setattr(env, "load_environment_accounts", lambda: candidates)
    monkeypatch.setattr(env, "_open_fresh_login", lambda *a: events.append("fresh-login"))
    monkeypatch.setattr(env, "_tap", lambda *a: events.append("me"))
    monkeypatch.setattr(env, "_visible_id", lambda *a: True)
    monkeypatch.setattr(env, "_wait", lambda condition, timeout=12: condition())
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda *a, **kw: pytest.fail("App environment detection must not request any API"))
    monkeypatch.setattr(auth, "_tap_home_tab", lambda *a, **kw: events.append("home"))
    monkeypatch.setattr(env, "attach_text", lambda name, text: events.append(json.loads(text)))
    return driver, events


def test_first_rejection_then_success_binds_same_credentials_and_caches(monkeypatch, candidates, detection):
    driver, events = detection
    attempts = []
    def fresh_login(*args):
        events.append("fresh-login")
        driver.page_source = "<root/>"
    monkeypatch.setattr(env, "_open_fresh_login", fresh_login)
    def login(driver, username, password, *, resubmit):
        assert resubmit is False
        attempts.append(password)
        if password == candidates[0].password:
            driver.page_source = '<root><XCUIElementTypeStaticText name="密码错误"/></root>'
            raise auth.LoginRejected("password rejected")
        assert not auth._password_rejected_from_page_source(driver.page_source)
    monkeypatch.setattr(auth, "_perform_password_login", login)
    assert env.detect_app_environment(driver, Config()) == candidates[1]
    assert attempts == [a.password for a in candidates]
    assert env.effective_login_config(driver, Config()) == Config("phone", "prod-password")
    # A cached session remains bound even if the config changes later.
    monkeypatch.setattr(env, "load_environment_accounts", lambda: pytest.fail("must not re-read configuration"))
    assert env.detect_app_environment(driver, Config()) == candidates[1]
    assert events.count("fresh-login") == 2
    assert "prod-password" not in str(events)


def test_all_app_rejections_stop_before_publication(monkeypatch, detection):
    driver, _ = detection
    def reject(*args, **kwargs):
        raise auth.LoginRejected("rejected")
    monkeypatch.setattr(auth, "_perform_password_login", reject)
    with pytest.raises(AssertionError, match="None of the configured"):
        env.detect_app_environment(driver, Config())
    assert not hasattr(driver, "_environment_login_selection")


def test_login_timeout_is_not_a_credential_rejection(monkeypatch, detection):
    driver, _ = detection
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise AssertionError("Login page remained visible")
    monkeypatch.setattr(auth, "_perform_password_login", timeout)
    with pytest.raises(AssertionError, match="remained visible"):
        env.detect_app_environment(driver, Config())
    assert len(calls) == 1


def test_form_disappearance_without_authenticated_page_is_not_success(monkeypatch, detection):
    driver, _ = detection
    monkeypatch.setattr(auth, "_perform_password_login", lambda *a, **kw: None)
    monkeypatch.setattr(env, "_visible_id", lambda *a: False)
    with pytest.raises(AssertionError, match="without an authenticated"):
        env.detect_app_environment(driver, Config())
    assert not hasattr(driver, "_environment_login_selection")


def test_app_success_binds_configured_api_without_network_verification(monkeypatch, candidates, detection):
    driver, events = detection
    monkeypatch.setattr(auth, "_perform_password_login", lambda *a, **kw: None)
    assert env.detect_app_environment(driver, Config()) == candidates[0]
    assert {"environment": "test", "api_base_url": candidates[0].api_base_url,
            "result": "app-login-matched"} in events


def test_cleanup_uses_app_matched_environment_instead_of_static_config(monkeypatch, candidates):
    selected = candidates[0]
    calls = []
    monkeypatch.setattr(api, "delete_note_via_api", lambda *a, **kw: calls.append((a, kw)))
    driver = SimpleNamespace(_environment_login_selection=selected, _api_note_publication_login=selected,
                             _api_note_publication={"requested_title": "title", "published_title": "unique-title", "post_id": "post-id"})
    report = cleanup.cleanup_published_note_via_api(driver, "title", Config())
    assert calls == [(("post-id", selected.username, selected.password), {"base_url": selected.api_base_url})]
    assert report.deleted == ["title"]


def test_cleanup_refuses_login_changed_since_publication(monkeypatch, candidates):
    monkeypatch.setattr(api, "delete_note_via_api", lambda *a, **kw: pytest.fail("must not delete"))
    driver = SimpleNamespace(_environment_login_selection=candidates[1], _api_note_publication_login=candidates[0],
                             _api_note_publication={"requested_title": "title", "published_title": "title", "post_id": "post-id"})
    with pytest.raises(api.NoteCleanupApiError, match="login changed"):
        cleanup.cleanup_published_note_via_api(driver, "title", Config())


@pytest.mark.parametrize("source,expected", [
    ('<root><node name="me-settings-button"/></root>', True),
    ('<root visible="false"><node name="me-settings-button"/></root>', False),
    ('<root><node name="old me-settings-button"/></root>', False),
])
def test_authenticated_marker_must_be_visible_and_exact(source, expected):
    assert env._visible_id(SimpleNamespace(page_source=source), "me-settings-button") is expected


@pytest.mark.parametrize("already_logged_in", [True, False])
def test_detection_requires_real_logout_instead_of_reusing_session(monkeypatch, already_logged_in):
    events = []
    login = '<root><node name="login-phone-input"/><node name="login-primary-button"/></root>'
    profile = '<root><node name="me-settings-button"/></root>'
    class Driver:
        page_source = profile if already_logged_in else login

        def terminate_app(self, bundle):
            events.append("restart")

        def activate_app(self, bundle):
            pass

    driver = Driver()
    def tap(driver, identifier, text):
        events.append(identifier)
        if identifier == "me-confirm-submit":
            driver.page_source = login
    monkeypatch.setattr(env, "_tap", tap)
    monkeypatch.setattr(env, "_confirm_logout", lambda driver: tap(driver, "me-confirm-submit", "退出登录"))
    monkeypatch.setattr(env, "_wait", lambda condition, timeout=12: condition())
    env._open_fresh_login(driver, SimpleNamespace(bundle_id="app"))
    assert ("me-settings-logout" in events) is already_logged_in
    assert ("me-confirm-submit" in events) is already_logged_in
    assert auth._login_form_visible_from_page_source(driver.page_source)


def test_old_ios_me_page_settings_uses_unique_header_control():
    taps = []
    class Driver:
        page_source = '''<root><node name="me-page" label="我的笔记 个人资料" x="0" y="0" width="402">
          <node x="316" y="75" width="30" height="30"/>
          <node x="359" y="75" width="30" height="30"><node x="365" y="81" width="18" height="18"/></node>
          <node x="359" y="500" width="30" height="30"/>
          <node visible="false"><node x="380" y="75" width="30" height="30"/></node>
        </node></root>'''

        def execute_script(self, command, arguments):
            taps.append((command, arguments))
    driver = Driver()
    assert env._authenticated_me_visible(driver)
    env._tap_settings(driver)
    assert taps == [("mobile: tap", {"x": 374, "y": 90})]


@pytest.mark.parametrize("source", [
    '<root label="我的笔记 个人资料"><node x="359" y="75" width="30" height="30"/></root>',
    '<root visible="false"><node name="me-page" label="我的笔记 个人资料"/></root>',
    '<root><node name="me-page" label="登录后查看个人中心"/></root>',
])
def test_old_ios_profile_requires_visible_authenticated_page(source):
    driver = SimpleNamespace(page_source=source)
    assert not env._authenticated_me_visible(driver)
    with pytest.raises(AssertionError, match="outside an authenticated"):
        env._tap_settings(driver)


def test_old_logout_confirmation_uses_only_visible_dialog_text(monkeypatch):
    calls = []
    class Driver:
        page_source = '<root><node name="退出登录" visible="false"/><node name="您确定要退出登录吗？"/></root>'

        def find_element(self, by, value):
            calls.append((by, value))
            return SimpleNamespace(click=lambda: calls.append("click"))
    monkeypatch.setattr(env, "_wait", lambda condition, timeout=12: condition())
    env._confirm_logout(Driver())
    assert "visible == true" in calls[0][1]
    assert calls[-1] == "click"


def android_me_source(*, hidden_profile=False, hidden_labels=False):
    return f'''<hierarchy><android.view.ViewGroup resource-id="me-page" bounds="[0,152][1280,2558]" displayed="{str(not hidden_profile).lower()}">
      <android.view.ViewGroup bounds="[1007,194][1101,289]"/>
      <android.view.ViewGroup bounds="[1144,194][1238,289]"/>
      <android.view.ViewGroup bounds="[1144,900][1238,995]"/>
      <android.view.ViewGroup displayed="false"><node bounds="[1180,194][1274,289]"/></android.view.ViewGroup>
      <android.view.ViewGroup displayed="{str(not hidden_labels).lower()}">
        <android.widget.TextView text="我的笔记"/><android.widget.TextView text="个人资料"/>
      </android.view.ViewGroup>
    </android.view.ViewGroup></hierarchy>'''


@pytest.mark.parametrize("hidden_profile,hidden_labels,expected", [(False, False, True), (True, False, False), (False, True, False)])
def test_android_authenticated_me_uses_visible_descendants(hidden_profile, hidden_labels, expected):
    driver = SimpleNamespace(page_source=android_me_source(hidden_profile=hidden_profile, hidden_labels=hidden_labels))
    assert env._authenticated_me_visible(driver) is expected


def test_android_settings_uses_bounded_header_geometry_and_android_gesture():
    calls = []
    driver = SimpleNamespace(page_source=android_me_source(), capabilities={"platformName": "Android"},
                             execute_script=lambda *args: calls.append(args))
    env._tap_settings(driver)
    assert calls == [("mobile: clickGesture", {"x": 1191, "y": 241})]


def test_android_settings_does_not_use_icons_outside_visible_me_page():
    source = android_me_source(hidden_profile=True)
    with pytest.raises(AssertionError, match="no identifiable"):
        env._android_settings_point(source)


def test_android_logout_only_clicks_unique_visible_confirmation(monkeypatch):
    calls = []
    button = SimpleNamespace(is_displayed=lambda: True, click=lambda: calls.append("click"))
    hidden = SimpleNamespace(is_displayed=lambda: False)
    driver = SimpleNamespace(page_source='<hierarchy><node text="您确定要退出登录吗？"/></hierarchy>',
                             capabilities={"platformName": "Android"},
                             find_elements=lambda *a: [hidden, button])
    monkeypatch.setattr(env, "_wait", lambda predicate, timeout=12: predicate())
    env._confirm_logout(driver)
    assert calls == ["click"]
    driver.find_elements = lambda *a: [button, button]
    with pytest.raises(AssertionError, match="ambiguous"):
        env._confirm_logout(driver)
