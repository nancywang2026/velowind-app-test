from __future__ import annotations

from dataclasses import dataclass
import time
from xml.etree import ElementTree

from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from velowind_appium.actions import tap_text_if_present
import velowind_appium.modules.draft_flow as draft_flow


@dataclass(frozen=True)
class ProfileSnapshot:
    page_visible: bool
    avatar_visible: bool
    nickname_visible: bool
    phone_visible: bool
    real_name_status_visible: bool
    birthday_visible: bool

    def merge(self, other: "ProfileSnapshot") -> "ProfileSnapshot":
        return ProfileSnapshot(
            page_visible=self.page_visible or other.page_visible,
            avatar_visible=self.avatar_visible or other.avatar_visible,
            nickname_visible=self.nickname_visible or other.nickname_visible,
            phone_visible=self.phone_visible or other.phone_visible,
            real_name_status_visible=self.real_name_status_visible or other.real_name_status_visible,
            birthday_visible=self.birthday_visible or other.birthday_visible,
        )

    def is_basic_profile_visible(self) -> bool:
        return all(
            [
                self.page_visible,
                self.avatar_visible,
                self.nickname_visible,
                self.phone_visible,
                self.real_name_status_visible,
                self.birthday_visible,
            ]
        )


PREFERENCE_OPTION_TEXTS = ["骑行", "徒步", "滑雪", "登山", "空中运动", "水上运动", "跑步"]
COUPON_STATUS_TEXTS = ["未使用", "已使用", "已失效", "已过期"]


@dataclass(frozen=True)
class InterestPreferencesSnapshot:
    page_visible: bool
    visible_options: list[str]

    def is_basic_preferences_visible(self) -> bool:
        return self.page_visible and len(self.visible_options) >= 2


@dataclass(frozen=True)
class MyCouponsSnapshot:
    page_visible: bool
    visible_statuses: list[str]

    def is_basic_coupons_visible(self) -> bool:
        return self.page_visible and len(self.visible_statuses) >= 2


@dataclass(frozen=True)
class AccountSecuritySnapshot:
    page_visible: bool
    phone_visible: bool
    login_status_visible: bool
    password_entry_visible: bool
    real_name_status_visible: bool
    account_deletion_warning_visible: bool

    def is_basic_account_security_visible(self) -> bool:
        return all(
            [
                self.page_visible,
                self.phone_visible,
                self.login_status_visible,
                self.password_entry_visible,
                self.real_name_status_visible,
                self.account_deletion_warning_visible,
            ]
        )


@dataclass(frozen=True)
class LeaderApplicationSnapshot:
    page_visible: bool
    introduction_visible: bool
    benefits_visible: bool
    notice_visible: bool
    status_visible: bool

    def is_basic_leader_application_visible(self) -> bool:
        return all(
            [
                self.page_visible,
                self.introduction_visible,
                self.benefits_visible,
                self.notice_visible,
                self.status_visible,
            ]
        )


def open_profile_page(driver: WebDriver, timeout: int = 15) -> ProfileSnapshot:
    snapshot = parse_profile_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_profile_visible():
        return snapshot

    draft_flow.open_me_page(driver, timeout=timeout)
    if not _tap_profile_entry(driver):
        raise AssertionError("Unable to tap the profile entry from Me page")

    end_at = time.monotonic() + timeout
    snapshot = parse_profile_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = snapshot.merge(parse_profile_snapshot(_safe_page_source(driver)))
        if snapshot.is_basic_profile_visible():
            return snapshot
        _swipe_profile_up(driver)
        time.sleep(0.3)
    raise AssertionError(f"Profile page did not expose expected fields: {snapshot}")


def open_interest_preferences_page(driver: WebDriver, timeout: int = 15) -> InterestPreferencesSnapshot:
    snapshot = parse_interest_preferences_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_preferences_visible():
        return snapshot

    draft_flow.open_me_page(driver, timeout=timeout)
    if not _tap_interest_preferences_entry(driver):
        raise AssertionError("Unable to tap the interest preferences entry from Me page")

    end_at = time.monotonic() + timeout
    snapshot = parse_interest_preferences_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = parse_interest_preferences_snapshot(_safe_page_source(driver))
        if snapshot.is_basic_preferences_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"Interest preferences page did not expose expected options: {snapshot}")


def open_my_coupons_page(driver: WebDriver, timeout: int = 15) -> MyCouponsSnapshot:
    snapshot = parse_my_coupons_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_coupons_visible():
        return snapshot

    draft_flow.open_me_page(driver, timeout=timeout)
    if not _tap_my_coupons_entry(driver):
        raise AssertionError("Unable to tap the My Coupons entry from Me page")

    end_at = time.monotonic() + timeout
    snapshot = parse_my_coupons_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = parse_my_coupons_snapshot(_safe_page_source(driver))
        if snapshot.is_basic_coupons_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"My Coupons page did not expose expected statuses: {snapshot}")


def open_account_security_page(driver: WebDriver, timeout: int = 15) -> AccountSecuritySnapshot:
    snapshot = parse_account_security_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_account_security_visible():
        return snapshot

    draft_flow.open_me_page(driver, timeout=timeout)
    if not _tap_settings_entry(driver):
        raise AssertionError("Unable to tap the Settings entry from Me page")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if "账号与安全" in " ".join(_extract_texts(_safe_page_source(driver), visible_only=True)):
            break
        time.sleep(0.3)
    else:
        raise AssertionError("Settings page did not expose the Account Security entry")

    if not _tap_account_security_entry(driver):
        raise AssertionError("Unable to tap the Account Security entry from Settings page")

    end_at = time.monotonic() + timeout
    snapshot = parse_account_security_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = parse_account_security_snapshot(_safe_page_source(driver))
        if snapshot.is_basic_account_security_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"Account Security page did not expose expected fields: {snapshot}")


def open_leader_application_page(driver: WebDriver, timeout: int = 15) -> LeaderApplicationSnapshot:
    snapshot = parse_leader_application_snapshot(_safe_page_source(driver))
    if snapshot.is_basic_leader_application_visible():
        return snapshot

    draft_flow.open_me_page(driver, timeout=timeout)
    if not _tap_settings_entry(driver):
        raise AssertionError("Unable to tap the Settings entry from Me page")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if "成为领队" in " ".join(_extract_texts(_safe_page_source(driver), visible_only=True)):
            break
        time.sleep(0.3)
    else:
        raise AssertionError("Settings page did not expose the Leader Application entry")

    if not _tap_leader_application_entry(driver):
        raise AssertionError("Unable to tap the Leader Application entry from Settings page")

    end_at = time.monotonic() + timeout
    snapshot = parse_leader_application_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = parse_leader_application_snapshot(_safe_page_source(driver))
        if snapshot.is_basic_leader_application_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"Leader Application page did not expose expected content: {snapshot}")


def parse_profile_snapshot(page_source: str) -> ProfileSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_text = " ".join(visible_texts)
    page_visible = any(text in joined_text for text in ["个人资料", "编辑资料"])
    return ProfileSnapshot(
        page_visible=page_visible,
        avatar_visible="头像" in joined_text or (page_visible and _visible_image_present(page_source)),
        nickname_visible=any(text in joined_text for text in ["昵称", "用户名"]),
        phone_visible=any(text in joined_text for text in ["手机号", "手机号码"]),
        real_name_status_visible=any(text in joined_text for text in ["实名认证", "实名状态", "已实名", "未实名"]),
        birthday_visible="生日" in joined_text,
    )


def parse_my_coupons_snapshot(page_source: str) -> MyCouponsSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_text = " ".join(visible_texts)
    return MyCouponsSnapshot(
        page_visible=any(text in joined_text for text in ["我的卡券", "优惠券", "卡券"]),
        visible_statuses=[text for text in COUPON_STATUS_TEXTS if text in joined_text],
    )


def parse_interest_preferences_snapshot(page_source: str) -> InterestPreferencesSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_text = " ".join(visible_texts)
    return InterestPreferencesSnapshot(
        page_visible="兴趣偏好" in joined_text,
        visible_options=[text for text in PREFERENCE_OPTION_TEXTS if text in joined_text],
    )


def parse_account_security_snapshot(page_source: str) -> AccountSecuritySnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_text = " ".join(visible_texts)
    return AccountSecuritySnapshot(
        page_visible="账号与安全" in joined_text,
        phone_visible="绑定手机号" in joined_text,
        login_status_visible="登录状态" in joined_text and any(text in joined_text for text in ["已登录", "未登录"]),
        password_entry_visible=any(text in joined_text for text in ["设置/修改密码", "修改密码", "设置密码"]),
        real_name_status_visible="实名认证" in joined_text and any(text in joined_text for text in ["已认证", "未认证"]),
        account_deletion_warning_visible="账号注销" in joined_text and any(
            text in joined_text for text in ["危险操作", "短信验证码", "注销账号"]
        ),
    )


def parse_leader_application_snapshot(page_source: str) -> LeaderApplicationSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_text = " ".join(visible_texts)
    return LeaderApplicationSnapshot(
        page_visible="成为领队" in joined_text,
        introduction_visible="寻风集领队" in joined_text,
        benefits_visible=any(text in joined_text for text in ["领队培训", "标准流程", "品牌背书", "资源对接"]),
        notice_visible="温馨提示" in joined_text and "提交申请后" in joined_text,
        status_visible="申请状态" in joined_text and any(
            text in joined_text for text in ["您已经成为领队", "提交申请", "审核"]
        ),
    )


def _tap_profile_entry(driver: WebDriver) -> bool:
    for text in ["个人资料", "编辑资料"]:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return _tap_by_ratio(driver, 0.50, 0.62)


def _tap_interest_preferences_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "兴趣偏好", timeout=2):
        return True
    return _tap_by_ratio(driver, 0.50, 0.69)


def _tap_my_coupons_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "我的卡券", timeout=2):
        return True
    return _tap_by_ratio(driver, 0.50, 0.47)


def _tap_settings_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "设置", timeout=1):
        return True
    return _tap_by_ratio(driver, 0.93, 0.105)


def _tap_account_security_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "账号与安全", timeout=2):
        return True
    return _tap_by_ratio(driver, 0.56, 0.30)


def _tap_leader_application_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "成为领队", timeout=2):
        return True
    return _tap_by_ratio(driver, 0.54, 0.42)


def _swipe_profile_up(driver: WebDriver) -> bool:
    try:
        driver.execute_script("mobile: swipe", {"direction": "up"})
        return True
    except (AttributeError, WebDriverException):
        return False


def _tap_by_ratio(driver: WebDriver, x_ratio: float, y_ratio: float) -> bool:
    try:
        rect = driver.get_window_rect()
        driver.execute_script(
            "mobile: tap",
            {
                "x": int(rect["width"] * x_ratio),
                "y": int(rect["height"] * y_ratio),
            },
        )
        return True
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _extract_texts(page_source: str, *, visible_only: bool) -> list[str]:
    if not page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return [" ".join(page_source.split())]

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if visible_only and (
            element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false"
        ):
            continue
        raw_text = (
            element.attrib.get("text", "")
            or element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        )
        normalized = " ".join(raw_text.split())
        if not normalized or normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    return texts


def _visible_image_present(page_source: str) -> bool:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return "XCUIElementTypeImage" in page_source
    for element in root.iter():
        if not element.tag.endswith("Image") and element.attrib.get("type") not in {"XCUIElementTypeImage", "android.widget.ImageView"}:
            continue
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        return True
    return False


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except (AttributeError, WebDriverException):
        return ""
