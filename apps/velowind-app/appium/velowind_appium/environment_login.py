"""Identify the installed App through an actual, environment-specific login."""
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

import yaml
from appium.webdriver.common.appiumby import AppiumBy

from . import auth
from .actions import tap_accessibility_id_or_text_if_present
from .cleanup_config import normalize_note_api_base_url
from .config import _read_yaml_config
from .reporting import attach_text


DEFAULT_ENVIRONMENT_ACCOUNTS = Path(__file__).resolve().parents[4] / ".private/message-regression/app-environments.yaml"


@dataclass(frozen=True)
class EnvironmentAccount:
    environment: str
    api_base_url: str
    username: str = field(repr=False)
    password: str = field(repr=False)


def load_environment_accounts():
    """Return None when disabled; validate every candidate before touching the App."""
    path = os.environ.get("VW_APPIUM_ENVIRONMENT_ACCOUNTS")
    if path is None:
        if os.environ.get("VW_APPIUM_PLATFORM", "ios").strip().lower() == "android":
            from .android_config import _read_yaml_config as read_config
        else:
            read_config = _read_yaml_config
        setting = read_config().get("environment_login", {})
        path = setting.get("candidates_file") if isinstance(setting, dict) else None
    if (path is None and os.environ.get("VW_APPIUM_PLATFORM", "ios").strip().lower() != "ios"
            and os.environ.get("VW_API_ENV") is not None
            and os.environ["VW_API_ENV"].strip().lower() != "prod"
            and DEFAULT_ENVIRONMENT_ACCOUNTS.is_file()):
        path = DEFAULT_ENVIRONMENT_ACCOUNTS
    if path is None:
        return None
    manifest = Path(path).expanduser()
    try:
        data = yaml.safe_load(manifest.read_text())
        entries = data["environments"]
        if not isinstance(entries, dict) or len(entries) < 2:
            raise ValueError()
        accounts = []
        for environment, entry in entries.items():
            if environment not in {"test", "uat", "prod"} or not isinstance(entry, dict):
                raise ValueError()
            config_path = Path(entry["config_file"]).expanduser()
            if not config_path.is_absolute():
                config_path = manifest.parent / config_path
            login = yaml.safe_load(config_path.read_text())["login"]
            if not isinstance(login, dict):
                raise ValueError()
            username, password = str(login.get("username") or "").strip(), str(login.get("password") or "")
            if not username or not password.strip():
                raise ValueError()
            accounts.append(EnvironmentAccount(environment, normalize_note_api_base_url(entry["api_base_url"]),
                                               username, password))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        raise ValueError("Invalid environment login configuration; each environment needs a config_file with login credentials and an HTTPS api_base_url") from None
    if len({(a.username, a.password) for a in accounts}) != len(accounts):
        raise ValueError("Environment login credentials must differ between environments")
    if len({a.api_base_url for a in accounts}) != len(accounts):
        raise ValueError("Environment login API addresses must differ between environments")
    preferred = os.environ.get("VW_API_ENV")
    if preferred is not None:
        preferred = preferred.strip().lower()
        if preferred not in {a.environment for a in accounts}:
            raise ValueError("VW_API_ENV must name an environment present in the login candidates")
        accounts.sort(key=lambda account: account.environment != preferred)
    return accounts


def effective_login_config(driver, config):
    selected = getattr(driver, "_environment_login_selection", None)
    if selected is None:
        return config
    return replace(config, login_username=selected.username, login_password=selected.password)


def _wait(predicate, timeout=12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.3)
    return False


def _visible_id(driver, identifier):
    # Native trees can retain hidden login and profile pages behind the active screen.
    root = ET.fromstring(driver.page_source)
    def visit(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return False
        return any(node.get(k) == identifier for k in ("name", "resource-id", "content-desc", "text")) or any(visit(child) for child in node)
    return visit(root)


def _authenticated_me_visible(driver):
    if _visible_id(driver, "me-settings-button"):
        return True
    root = ET.fromstring(driver.page_source)
    def visible_labels(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return ""
        return " ".join([node.get("label", ""), node.get("text", ""),
                         node.get("content-desc", ""), *(visible_labels(child) for child in node)])
    def visit(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return False
        if node.get("name") == "me-page" or node.get("resource-id") == "me-page":
            label = visible_labels(node)
            return "我的笔记" in label and "个人资料" in label
        return any(visit(child) for child in node)
    return visit(root)


def _is_android(driver):
    return str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() == "android"


def _android_settings_point(source):
    root = ET.fromstring(source)
    def rect(node):
        match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", node.get("bounds", ""))
        if match is None:
            return None
        x, y, right, bottom = map(int, match.groups())
        return x, y, right-x, bottom-y
    candidates = set()
    def visit(node, page=None):
        if node.get("displayed") == "false" or node.get("visible") == "false":
            return
        if node.get("resource-id") == "me-page":
            page = rect(node)
        bounds = rect(node)
        if page and bounds and node.get("enabled") != "false":
            px, py, pw, ph = page
            x, y, w, h = bounds
            # The old Android build exposes unlabeled header icons in pixels.
            # Scale the size/header limits with the page width, not iOS points.
            if (.055*pw <= w <= .12*pw and .055*pw <= h <= .12*pw
                    and abs(w-h) <= .01*pw and x > px+.75*pw
                    and py <= y and y+h <= min(py+.30*pw, py+ph)
                    and x+w <= px+pw):
                candidates.add(bounds)
        for child in node:
            visit(child, page)
    visit(root)
    if not candidates:
        raise AssertionError("Authenticated Me page has no identifiable settings control")
    right = max(x for x, _, _, _ in candidates)
    matches = [r for r in candidates if r[0] == right]
    if len(matches) != 1:
        raise AssertionError("Me settings control is ambiguous")
    x, y, w, h = matches[0]
    return int(x+w/2), int(y+h/2)


def _tap_settings(driver):
    if _visible_id(driver, "me-settings-button"):
        _tap(driver, "me-settings-button", "设置")
        return
    # Older iOS builds expose the gear as an unlabeled 30pt square. Only use
    # geometry within the verified Me page, selecting its rightmost header icon.
    if not _authenticated_me_visible(driver):
        raise AssertionError("Cannot locate settings outside an authenticated Me page")
    if _is_android(driver):
        x, y = _android_settings_point(driver.page_source)
        driver.execute_script("mobile: clickGesture", {"x": x, "y": y})
        return
    root = ET.fromstring(driver.page_source)
    pages = [n for n in root.iter() if n.get("name") == "me-page" and n.get("visible") != "false"]
    candidates = set()
    for page in pages:
        px, py, pw = (float(page.get(k, "0")) for k in ("x", "y", "width"))
        def visit(node):
            if node.get("visible") == "false":
                return
            x, y, w, h = (float(node.get(k, "0")) for k in ("x", "y", "width", "height"))
            if 24 <= w <= 48 and 24 <= h <= 48 and abs(w-h) <= 2 and x > px+pw*.75 and py <= y <= py+120:
                candidates.add((x, y, w, h))
            for child in node:
                visit(child)
        visit(page)
    if not candidates:
        raise AssertionError("Authenticated Me page has no identifiable settings control")
    right = max(x for x, _, _, _ in candidates)
    matches = [r for r in candidates if r[0] == right]
    if len(matches) != 1:
        raise AssertionError("Me settings control is ambiguous")
    x, y, w, h = matches[0]
    driver.execute_script("mobile: tap", {"x": int(x+w/2), "y": int(y+h/2)})


def _tap(driver, identifier, text):
    if not tap_accessibility_id_or_text_if_present(driver, identifier, text, timeout=5):
        raise AssertionError(f"Environment login could not open {identifier}")


def _confirm_logout(driver):
    if not _wait(lambda: _visible_id(driver, "me-confirm-submit")
                 or _visible_id(driver, "您确定要退出登录吗？")):
        raise AssertionError("Logout confirmation did not appear")
    if _visible_id(driver, "me-confirm-submit"):
        _tap(driver, "me-confirm-submit", "退出登录")
    elif _is_android(driver):
        elements = driver.find_elements(AppiumBy.ANDROID_UIAUTOMATOR,
                                        'new UiSelector().text("退出登录")')
        visible = [element for element in elements if element.is_displayed()]
        if len(visible) != 1:
            raise AssertionError("Logout confirmation action is ambiguous")
        visible[0].click()
    else:
        # The old iOS drawer retains its own hidden logout button. Target only
        # the visible dialog text, never the first underlying matching element.
        driver.find_element(AppiumBy.IOS_PREDICATE,
                            'type == "XCUIElementTypeStaticText" AND visible == true AND name == "退出登录"').click()


def _open_fresh_login(driver, config):
    # Restarting the App returns to its root while preserving photos permission.
    bundle = getattr(config, "bundle_id", None) or getattr(config, "app_package", None)
    if bundle:
        driver.terminate_app(bundle)
        driver.activate_app(bundle)
    _tap(driver, "bottom-nav-me", "我的")
    if not _wait(lambda: auth.login_required_from_page_source(driver.page_source)
                 or _authenticated_me_visible(driver)):
        raise AssertionError("Environment login could not identify the Me or login page")
    if not auth.login_required_from_page_source(driver.page_source):
        _tap_settings(driver)
        _tap(driver, "me-settings-logout", "退出登录")
        _confirm_logout(driver)
    if not _wait(lambda: auth._login_form_visible_from_page_source(driver.page_source)):
        raise AssertionError("Environment detection requires a fresh login form; existing session is not evidence")


def detect_app_environment(driver, config):
    if getattr(driver, "_environment_login_selection", None) is not None:
        return driver._environment_login_selection
    accounts = load_environment_accounts()
    if accounts is None:
        return None
    attach_text("app-environment-login-order", json.dumps({
        "preferred_environment": os.environ.get("VW_API_ENV"),
        "candidate_order": [account.environment for account in accounts],
    }))
    _open_fresh_login(driver, config)
    for index, account in enumerate(accounts):
        try:
            auth._perform_password_login(driver, account.username, account.password, resubmit=False)
        except auth.LoginRejected:
            attach_text("app-environment-login", json.dumps({"environment": account.environment, "result": "app-rejected"}))
            if index + 1 < len(accounts):
                # Password errors can be inline and persist until the next
                # submission. A fresh form prevents that stale error from
                # being attributed to the next candidate's request.
                _open_fresh_login(driver, config)
                if not _wait(lambda: auth._login_rejection_reason(driver.page_source) is None):
                    raise AssertionError("Previous login rejection remained visible on a fresh login form")
            continue
        _tap(driver, "bottom-nav-me", "我的")
        if not _wait(lambda: _authenticated_me_visible(driver)):
            raise AssertionError("Login form disappeared without an authenticated Me page")
        driver._environment_login_selection = account
        attach_text("app-environment-login", json.dumps({"environment": account.environment,
                    "api_base_url": account.api_base_url, "result": "app-login-matched"}))
        auth._tap_home_tab(driver, timeout=5)
        return account
    raise AssertionError("None of the configured environment credentials could log in to the App")
