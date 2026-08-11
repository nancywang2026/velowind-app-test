from __future__ import annotations

from dataclasses import dataclass
import re
import time
from xml.etree import ElementTree

from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

from velowind_appium.actions import (
    swipe_vertical,
    tap_accessibility_id_or_text_if_present,
    tap_if_present,
    tap_text_if_present,
)
from velowind_appium.modules.rental_common import tap_by_coordinate_ratios


ACTIVITY_READY_IDS = ["activity-discovery-v2-page"]
ACTIVITY_READY_TEXTS = ["全部活动", "活动", "总里程", "难度等级"]
ACTIVITY_CATEGORY_TEXTS = ["全部活动", "骑行", "徒步", "滑雪", "登山", "空中运动", "水上运动", "跑步"]
ACTIVITY_CARD_MARKERS = ["总里程", "时长", "场次", "难度等级"]
ACTIVITY_SEARCH_ENTRY_IDS = ["activity-search-entry", "activity-search-button", "activity-discovery-search"]
ACTIVITY_SEARCH_INPUT_XPATHS = [
    '//XCUIElementTypeTextField[@value="请输入内容" or @placeholderValue="请输入内容" or contains(@value, "搜索")]',
    '//XCUIElementTypeSearchField[@value="请输入内容" or @placeholderValue="请输入内容" or contains(@value, "搜索")]',
    '//android.widget.EditText[@text="请输入内容" or @hint="请输入内容" or contains(@text, "搜索")]',
    '//android.widget.EditText',
]
ACTIVITY_SEARCH_SUBMIT_TEXTS = ["搜索", "Search"]
ACTIVITY_DETAIL_READY_IDS = ["activity-route-detail-v3-hero-carousel", "activity-detail-page"]
ACTIVITY_SIGNUP_READY_TEXTS = ["活动报名", "报名信息", "提交订单"]
ACTIVITY_SIGNUP_ACTION_TEXTS = ["确认报名", "立即报名"]
ACTIVITY_SIGNUP_UNAVAILABLE_TEXTS = ["报名结束", "名额已满", "已满员"]
ACTIVITY_ORDER_PAYMENT_TEXTS = ["支付中心", "确认支付", "订单支付", "去支付", "立即支付", "待支付"]
ACTIVITY_NETWORK_ERROR_TEXTS = ["加载失败", "网络连接异常", "Network Error"]
VIRTUAL_SIGNUP_ID_CARD_NUMBER = "110000199001010013"


@dataclass(frozen=True)
class ActivitySignupDraft:
    name: str
    certificate_type: str
    certificate_number: str
    phone: str


@dataclass(frozen=True)
class ActivityDetailSnapshot:
    title: str | None
    location: str | None
    publisher: str | None
    hero_image_visible: bool
    metrics_visible: bool
    tags_visible: bool
    route_visible: bool
    comments_visible: bool
    sessions_visible: bool

    def merge(self, other: "ActivityDetailSnapshot") -> "ActivityDetailSnapshot":
        return ActivityDetailSnapshot(
            title=self.title or other.title,
            location=self.location or other.location,
            publisher=self.publisher or other.publisher,
            hero_image_visible=self.hero_image_visible or other.hero_image_visible,
            metrics_visible=self.metrics_visible or other.metrics_visible,
            tags_visible=self.tags_visible or other.tags_visible,
            route_visible=self.route_visible or other.route_visible,
            comments_visible=self.comments_visible or other.comments_visible,
            sessions_visible=self.sessions_visible or other.sessions_visible,
        )

    def is_basic_detail_complete(self) -> bool:
        return all(
            [
                self.title,
                self.location,
                self.publisher,
                self.hero_image_visible,
                self.metrics_visible,
                self.tags_visible,
                self.route_visible,
                self.comments_visible,
                self.sessions_visible,
            ]
        )


@dataclass(frozen=True)
class ActivitySignupSnapshot:
    title_visible: bool
    meeting_location: str | None
    schedule_visible: bool
    quota_visible: bool
    services_visible: bool
    registration_fields_visible: bool
    rules_visible: bool
    fee_visible: bool
    submit_order_visible: bool
    name: str | None = None
    certificate_type: str | None = None
    certificate_number: str | None = None
    phone: str | None = None
    self_registration_selected: bool = False

    def is_basic_signup_complete(self) -> bool:
        return all(
            [
                self.title_visible,
                self.meeting_location,
                self.schedule_visible,
                self.quota_visible,
                self.services_visible,
                self.registration_fields_visible,
                self.rules_visible,
                self.fee_visible,
                self.submit_order_visible,
            ]
        )

    def matches_draft(self, draft: ActivitySignupDraft) -> bool:
        return (
            self.name == draft.name
            and self.certificate_type == draft.certificate_type
            and self.certificate_number == draft.certificate_number
            and self.phone == draft.phone
        )


@dataclass(frozen=True)
class ActivityOrderSnapshot:
    payment_page_visible: bool
    payment_method_visible: bool
    amount_visible: bool
    payment_action_visible: bool
    order_status_visible: bool

    def is_order_submission_complete(self) -> bool:
        return self.payment_page_visible and self.amount_visible and (
            self.payment_action_visible or self.order_status_visible
        )


@dataclass(frozen=True)
class MyActivitySignupSnapshot:
    page_visible: bool
    signup_tab_visible: bool
    registration_visible: bool
    status: str | None
    payment_action_visible: bool

    def is_signup_status_visible(self) -> bool:
        return self.page_visible and self.signup_tab_visible and self.registration_visible and bool(self.status)


@dataclass(frozen=True)
class MyActivityReactionSnapshot:
    page_visible: bool
    tab_visible: bool
    list_item_visible: bool
    empty_state_visible: bool

    def is_basic_reaction_list_visible(self) -> bool:
        return self.page_visible and self.tab_visible and (self.list_item_visible or self.empty_state_visible)


class ActivitySignupAlreadyExistsError(AssertionError):
    pass


def build_activity_signup_draft() -> ActivitySignupDraft:
    return ActivitySignupDraft(
        name="自动化报名测试",
        certificate_type="身份证",
        certificate_number=VIRTUAL_SIGNUP_ID_CARD_NUMBER,
        phone="13800138000",
    )


def open_activity_tab(driver: WebDriver, timeout: int = 20) -> None:
    if not tap_accessibility_id_or_text_if_present(driver, "bottom-nav-activity", "活动", timeout=5):
        raise AssertionError("Unable to tap the bottom activity tab")
    wait_for_activity_feed(driver, timeout=timeout)


def wait_for_activity_feed(driver: WebDriver, timeout: int = 20) -> str:
    reloaded_network_error = False
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if not reloaded_network_error and _activity_network_error_visible(page_source):
            reloaded_network_error = tap_text_if_present(driver, "重新加载", timeout=1)
            time.sleep(0.5)
            continue
        if _activity_ready_id_present(driver):
            return "activity-feed-id"
        if page_source and _activity_ready_text_present(page_source):
            return "activity-feed-text"
        time.sleep(0.2)
    raise TimeoutException("Activity feed did not become ready")


def switch_activity_category_navigation(driver: WebDriver, timeout: int = 10) -> None:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if "全部活动" in page_source and any(text in page_source for text in ACTIVITY_CATEGORY_TEXTS):
            return
        time.sleep(0.2)
    raise AssertionError("Unable to find the activity category navigation")


def select_activity_category(driver: WebDriver, category_name: str, timeout: int = 10) -> None:
    if not _tap_activity_category(driver, category_name):
        raise AssertionError(f"Unable to tap activity category: {category_name}")
    if not wait_for_activity_category_results(driver, category_name, timeout=timeout):
        raise AssertionError(f"Activity feed did not show {category_name} related activities")


def wait_for_activity_category_results(driver: WebDriver, category_name: str, timeout: int = 10) -> bool:
    reloaded_network_error = False
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if activity_feed_contains_category_results(page_source, category_name):
            return True
        if not reloaded_network_error and _activity_network_error_visible(page_source):
            reloaded_network_error = tap_text_if_present(driver, "重新加载", timeout=1)
            time.sleep(0.5)
            continue
        time.sleep(0.2)
    return False


def activity_feed_contains_category_results(page_source: str, category_name: str) -> bool:
    return bool(activity_feed_category_result_texts(page_source, category_name))


def activity_feed_category_result_texts(page_source: str, category_name: str) -> list[str]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    return [text for text in source_texts if _activity_card_matches_category(text, category_name)]


def activity_feed_all_results_match_category(page_source: str, category_name: str) -> tuple[bool, list[str]]:
    tag_texts = extract_visible_activity_category_tag_texts(page_source)
    source_texts = tag_texts or extract_visible_activity_card_texts(page_source)
    mismatched = [text for text in source_texts if not _activity_card_matches_category(text, category_name)]
    return bool(source_texts) and not mismatched, mismatched


def _activity_network_error_visible(page_source: str) -> bool:
    return "重新加载" in page_source and any(text in page_source for text in ACTIVITY_NETWORK_ERROR_TEXTS)


def open_activity_search(driver: WebDriver, timeout: int = 10) -> None:
    page_source = _safe_page_source(driver)
    if _activity_search_visible(page_source):
        return
    _tap_activity_search_entry_by_coordinate(driver, page_source=page_source)
    if _wait_until(lambda: _activity_search_visible(_safe_page_source(driver)), timeout=2):
        return
    for accessibility_id in ACTIVITY_SEARCH_ENTRY_IDS:
        if tap_if_present(driver, accessibility_id, timeout=1):
            break
    else:
        _tap_activity_search_entry_by_coordinate(driver, page_source=_safe_page_source(driver))
    if not _wait_until(lambda: _activity_search_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Activity search page did not appear")


def search_activities(driver: WebDriver, keyword: str, timeout: int = 15) -> None:
    search_input = _find_activity_search_input(driver, timeout=timeout)
    _replace_text(search_input, keyword)
    if not _tap_activity_search_submit(driver):
        raise AssertionError("Unable to submit activity search")
    if not wait_for_activity_text_search_results(driver, keyword, timeout=timeout):
        raise AssertionError(f"Activity search results did not appear for keyword: {keyword}")


def wait_for_activity_text_search_results(driver: WebDriver, keyword: str, timeout: int = 15) -> bool:
    return _wait_until(
        lambda: bool(activity_text_search_result_texts(_safe_page_source(driver), keyword)),
        timeout=timeout,
    )


def activity_text_search_result_texts(page_source: str, keyword: str) -> list[str]:
    normalized_keyword = " ".join(keyword.split())
    if not normalized_keyword:
        return []
    card_matches = [
        text
        for text in extract_visible_activity_card_texts(page_source)
        if normalized_keyword in text
    ]
    if card_matches:
        return card_matches
    return _android_visible_text_search_matches(page_source, normalized_keyword)


def _android_visible_text_search_matches(page_source: str, keyword: str) -> list[str]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []
    matches: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        text = element.attrib.get("text", "").strip()
        if not text or keyword not in text:
            continue
        if element.attrib.get("displayed") == "false" or element.attrib.get("visible") == "false":
            continue
        if text in ACTIVITY_CATEGORY_TEXTS or text in ACTIVITY_CARD_MARKERS:
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        matches.append(normalized)
        seen.add(normalized)
    return matches


def open_first_activity_detail(driver: WebDriver, timeout: int = 20) -> None:
    if activity_detail_is_visible(_safe_page_source(driver)):
        return
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        source = _safe_page_source(driver)
        if _tap_first_activity_card(
            driver,
            source,
            verify_open=lambda: activity_detail_is_visible(_safe_page_source(driver)),
            timeout=2,
        ):
            return
        time.sleep(0.3)
    raise AssertionError("Unable to open the first activity detail")


def open_first_signup_available_activity_detail(driver: WebDriver, timeout: int = 25) -> None:
    page_source = _safe_page_source(driver)
    if activity_detail_is_visible(page_source) and _activity_signup_action_available(page_source):
        return
    if activity_detail_is_visible(page_source):
        _return_to_activity_feed(driver)

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        for tap_points in _activity_card_tap_point_groups(page_source):
            if not _tap_activity_card_points(
                driver,
                tap_points,
                verify_open=lambda: activity_detail_is_visible(_safe_page_source(driver)),
                timeout=2,
            ):
                continue
            state = _wait_for_activity_detail_signup_state(driver, timeout=min(4, max(0.5, end_at - time.monotonic())))
            if state == "available":
                return
            _return_to_activity_feed(driver)
        if time.monotonic() >= end_at:
            break
        swipe_vertical(driver, "up")
        time.sleep(0.6)
    raise AssertionError("Unable to open a signup-capable activity detail")


def activity_detail_is_visible(page_source: str) -> bool:
    return any(marker in page_source for marker in ACTIVITY_DETAIL_READY_IDS) or (
        "路线说明" in page_source and "确认报名" in page_source
    ) or _android_activity_detail_loading_shell_visible(page_source)


def browse_activity_detail(driver: WebDriver, timeout: int = 25) -> ActivityDetailSnapshot:
    snapshot = read_activity_detail_snapshot(driver, timeout=timeout)
    if snapshot.is_basic_detail_complete():
        return snapshot

    for _ in range(4):
        swipe_vertical(driver, "up")
        time.sleep(0.6)
        snapshot = snapshot.merge(parse_activity_detail_snapshot(_safe_page_source(driver)))
        if snapshot.is_basic_detail_complete():
            return snapshot
    return snapshot


def open_activity_signup(driver: WebDriver, timeout: int = 20) -> None:
    if activity_signup_is_visible(_safe_page_source(driver)):
        return
    if not _tap_confirm_signup(driver):
        raise AssertionError("Unable to tap the activity signup action")
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if activity_signup_is_visible(page_source):
            return
        if _activity_signup_consent_prompt_visible(page_source):
            _tap_signup_consent(driver)
        time.sleep(0.3)
    raise AssertionError("Activity signup page did not become visible")


def activity_signup_is_visible(page_source: str) -> bool:
    return all(text in page_source for text in ACTIVITY_SIGNUP_READY_TEXTS)


def activity_signup_already_exists(page_source: str) -> bool:
    return "已经报名，无需重复报名" in page_source


def activity_signup_unavailable(page_source: str) -> bool:
    return any(text in page_source for text in ACTIVITY_SIGNUP_UNAVAILABLE_TEXTS)


def _activity_signup_consent_prompt_visible(page_source: str) -> bool:
    return all(text in page_source for text in ["报名提示", "同意并继续"])


def read_activity_signup_snapshot(driver: WebDriver, timeout: int = 20) -> ActivitySignupSnapshot:
    if not _wait_until(lambda: activity_signup_is_visible(_safe_page_source(driver)), timeout=timeout):
        raise AssertionError("Activity signup page did not become visible")
    return parse_activity_signup_snapshot(_safe_page_source(driver))


def fill_activity_signup_form(
    driver: WebDriver,
    draft: ActivitySignupDraft,
    timeout: int = 20,
) -> ActivitySignupSnapshot:
    if not activity_signup_is_visible(_safe_page_source(driver)):
        raise AssertionError("Activity signup page is not visible")

    snapshot = parse_activity_signup_snapshot(_safe_page_source(driver))
    if snapshot.self_registration_selected and snapshot.is_basic_signup_complete():
        return snapshot

    steps = [
        lambda: _fill_signup_text_field_by_placeholder(driver, "请输入报名人姓名", draft.name),
        lambda: _select_signup_certificate_type(driver, draft.certificate_type),
        lambda: _fill_signup_text_field_by_placeholder(driver, "请输入证件号码", draft.certificate_number),
        lambda: _fill_signup_text_field_by_placeholder(driver, "请输入通知手机号", draft.phone),
    ]
    for action in steps:
        if not action():
            raise AssertionError("Unable to fill the activity signup form")

    end_at = time.monotonic() + timeout
    snapshot = parse_activity_signup_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        snapshot = parse_activity_signup_snapshot(_safe_page_source(driver))
        if snapshot.matches_draft(draft):
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"Activity signup form did not echo the draft values: {snapshot}")


def submit_activity_signup_order(driver: WebDriver, timeout: int = 25) -> ActivityOrderSnapshot:
    if not _tap_submit_activity_order(driver):
        raise AssertionError("Unable to tap the activity signup submit order action")
    end_at = time.monotonic() + timeout
    snapshot = parse_activity_order_snapshot(_safe_page_source(driver))
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if activity_signup_already_exists(page_source):
            raise ActivitySignupAlreadyExistsError("The current account already has an activity signup for this session")
        snapshot = parse_activity_order_snapshot(page_source)
        if snapshot.is_order_submission_complete():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"Activity signup order submission did not reach payment/order page: {snapshot}")


def open_my_activity_signup_status(driver: WebDriver, timeout: int = 20) -> MyActivitySignupSnapshot:
    snapshot = parse_my_activity_signup_snapshot(_safe_page_source(driver))
    if snapshot.is_signup_status_visible():
        return snapshot

    if not _my_activity_page_visible(_safe_page_source(driver)):
        if not _tap_me_tab(driver):
            raise AssertionError("Unable to tap the Me tab")
        if not _wait_until(lambda: _me_page_visible(_safe_page_source(driver)), timeout=timeout):
            raise AssertionError("Me page did not become visible")
        if not _tap_my_activity_entry(driver):
            raise AssertionError("Unable to tap My Activity entry")
        if not _wait_until(lambda: _my_activity_page_visible(_safe_page_source(driver)), timeout=timeout):
            raise AssertionError("My Activity page did not become visible")

    if not _tap_my_activity_signup_tab(driver):
        raise AssertionError("Unable to tap My Activity signup tab")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        snapshot = parse_my_activity_signup_snapshot(_safe_page_source(driver))
        if snapshot.is_signup_status_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"My Activity signup status did not become visible: {snapshot}")


def open_my_activity_reaction_list(
    driver: WebDriver,
    *,
    tab_name: str,
    timeout: int = 20,
) -> MyActivityReactionSnapshot:
    snapshot = parse_my_activity_reaction_snapshot(_safe_page_source(driver), tab_name=tab_name)
    if snapshot.is_basic_reaction_list_visible():
        return snapshot

    if not _my_activity_page_visible(_safe_page_source(driver)):
        if not _tap_me_tab(driver):
            raise AssertionError("Unable to tap the Me tab")
        if not _wait_until(lambda: _me_page_visible(_safe_page_source(driver)), timeout=timeout):
            raise AssertionError("Me page did not become visible")
        if not _tap_my_activity_entry(driver):
            raise AssertionError("Unable to tap My Activity entry")
        if not _wait_until(lambda: _my_activity_page_visible(_safe_page_source(driver)), timeout=timeout):
            raise AssertionError("My Activity page did not become visible")

    if not _tap_my_activity_reaction_tab(driver, tab_name):
        raise AssertionError(f"Unable to tap My Activity {tab_name} tab")

    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        snapshot = parse_my_activity_reaction_snapshot(_safe_page_source(driver), tab_name=tab_name)
        if snapshot.is_basic_reaction_list_visible():
            return snapshot
        time.sleep(0.3)
    raise AssertionError(f"My Activity {tab_name} list did not become visible: {snapshot}")


def parse_activity_signup_snapshot(page_source: str) -> ActivitySignupSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)

    return ActivitySignupSnapshot(
        title_visible="活动报名" in joined_visible_text,
        meeting_location=_extract_signup_meeting_location(joined_visible_text),
        schedule_visible=bool(re.search(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", joined_visible_text)),
        quota_visible=all(text in joined_visible_text for text in ["活动名额", "剩余"]),
        services_visible="服务配置" in joined_visible_text,
        registration_fields_visible=(
            all(text in joined_visible_text for text in ["报名信息", "姓名", "证件类型", "证件号码", "通知手机号"])
            or all(text in joined_visible_text for text in ["报名信息", "本人"])
        ),
        rules_visible=all(text in joined_visible_text for text in ["报名规则", "取消规则", "报名说明"]),
        fee_visible="报名费用" in joined_visible_text and "¥" in joined_visible_text,
        submit_order_visible="提交订单" in joined_visible_text,
        name=_extract_signup_input_value_by_placeholder(page_source, "请输入报名人姓名")
        or _extract_signup_field_value(joined_visible_text, "姓名", ["证件类型"]),
        certificate_type=_extract_signup_certificate_type(joined_visible_text),
        certificate_number=_extract_signup_input_value_by_placeholder(page_source, "请输入证件号码")
        or _extract_signup_field_value(joined_visible_text, "证件号码", ["通知手机号"]),
        phone=_extract_signup_input_value_by_placeholder(page_source, "请输入通知手机号")
        or _extract_signup_field_value(joined_visible_text, "通知手机号", ["报名规则", "取消规则", "报名说明"]),
        self_registration_selected=all(text in joined_visible_text for text in ["报名信息", "本人"]),
    )


def read_activity_detail_snapshot(driver: WebDriver, timeout: int = 20) -> ActivityDetailSnapshot:
    end_at = time.monotonic() + timeout
    last_snapshot = ActivityDetailSnapshot(None, None, None, False, False, False, False, False, False)
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if not page_source:
            time.sleep(0.2)
            continue
        last_snapshot = parse_activity_detail_snapshot(page_source)
        if last_snapshot.is_basic_detail_complete():
            return last_snapshot
        if activity_detail_is_visible(page_source) and not _android_activity_detail_loading_shell_visible(page_source):
            return last_snapshot
        time.sleep(0.2)
    if last_snapshot.title or last_snapshot.location:
        return last_snapshot
    raise AssertionError("Activity detail page did not become visible")


def parse_activity_detail_snapshot(page_source: str) -> ActivityDetailSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)

    return ActivityDetailSnapshot(
        title=_extract_activity_detail_title(page_source, visible_texts),
        location=_first_text_containing(visible_texts, "省·"),
        publisher=_extract_activity_publisher(joined_visible_text),
        hero_image_visible=_activity_detail_hero_visible(page_source),
        metrics_visible=all(text in joined_visible_text for text in ["总里程", "参考时长", "风险等级"]),
        tags_visible=all(text in joined_visible_text for text in ["风景标签", "沿途景点"]),
        route_visible=_activity_detail_route_visible(joined_visible_text),
        comments_visible="活动评论" in joined_visible_text or "前往评论页查看真实活动评论" in joined_visible_text,
        sessions_visible=any(text in joined_visible_text for text in ["请选择场次", "场次信息", "集合地点", "暂无场次"]),
    )


def _android_activity_detail_loading_shell_visible(page_source: str) -> bool:
    return "活动详情" in page_source and "android.widget.ProgressBar" in page_source


def _activity_detail_route_visible(joined_visible_text: str) -> bool:
    if all(text in joined_visible_text for text in ["路线说明", "活动概览"]):
        return True
    if all(text in joined_visible_text for text in ["ROUTE", "路线说明"]):
        return True
    if all(text in joined_visible_text for text in ["路线说明", "活动评论"]):
        return True
    return "路线说明" in joined_visible_text and bool(re.search(r"\bDay\d+\b", joined_visible_text))


def parse_activity_order_snapshot(page_source: str) -> ActivityOrderSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)
    return ActivityOrderSnapshot(
        payment_page_visible=any(text in joined_visible_text for text in ["支付中心", "确认支付", "订单支付"]),
        payment_method_visible=any(text in joined_visible_text for text in ["微信支付", "支付宝", "支付方式"]),
        amount_visible="¥" in joined_visible_text or "报名费用" in joined_visible_text or "支付金额" in joined_visible_text,
        payment_action_visible=any(text in joined_visible_text for text in ["去支付", "立即支付", "确认支付"]),
        order_status_visible=any(text in joined_visible_text for text in ["待支付", "支付未完成", "报名成功", "报名待支付"]),
    )


def parse_my_activity_signup_snapshot(page_source: str) -> MyActivitySignupSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)
    status = next(
        (text for text in ["待支付", "支付未完成", "报名成功", "报名待支付", "已报名"] if text in joined_visible_text),
        None,
    )
    return MyActivitySignupSnapshot(
        page_visible="我的活动" in joined_visible_text,
        signup_tab_visible="报名" in joined_visible_text,
        registration_visible=status is not None or any(text in joined_visible_text for text in ["支付报名费", "报名详情"]),
        status=status,
        payment_action_visible=any(text in joined_visible_text for text in ["支付报名费", "去支付", "立即支付", "确认支付"]),
    )


def parse_my_activity_reaction_snapshot(page_source: str, *, tab_name: str) -> MyActivityReactionSnapshot:
    visible_texts = _extract_texts(page_source, visible_only=True)
    joined_visible_text = " ".join(visible_texts)
    empty_texts = [f"暂无{tab_name}活动", f"还没有{tab_name}", "暂无内容", "暂无数据"]
    return MyActivityReactionSnapshot(
        page_visible="我的活动" in joined_visible_text,
        tab_visible=tab_name in joined_visible_text,
        list_item_visible=any(text in joined_visible_text for text in ["总里程", "难度等级", "场次", "浙江省", "湖南省"]),
        empty_state_visible=any(text in joined_visible_text for text in empty_texts),
    )


def extract_visible_activity_category_tag_texts(page_source: str) -> list[str]:
    return [
        text
        for text in extract_visible_activity_card_texts(page_source)
        if _looks_like_activity_category_tag_text(text)
    ]


def extract_visible_activity_card_texts(page_source: str) -> list[str]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return _extract_activity_card_texts_from_plain_source(page_source)

    texts: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.attrib.get("visible") == "false":
            continue
        text = (
            element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
        ).strip()
        if not _looks_like_activity_card_text(text):
            continue
        normalized = " ".join(text.split())
        if normalized in seen:
            continue
        texts.append(normalized)
        seen.add(normalized)
    for text in _extract_android_activity_card_texts(root):
        if text in seen:
            continue
        texts.append(text)
        seen.add(text)
    return texts


def _extract_android_activity_card_texts(root: ElementTree.Element) -> list[str]:
    results: list[str] = []
    for element in root.iter():
        if not _android_single_activity_card_container(element):
            continue
        values = _android_descendant_texts(element)
        if any(_android_single_activity_card_container(child) for child in element) and not _android_card_context_values(values):
            continue
        category = next(value for value in values if value in ACTIVITY_CATEGORY_TEXTS[1:])
        ordered_values = (
            values
            if _android_card_context_values(values)
            else [category, *[value for value in values if value != category]]
        )
        results.append(" ".join(ordered_values))
    return results


def _android_descendant_texts(element: ElementTree.Element) -> list[str]:
    return [
        child.attrib.get("text", "").strip()
        for child in element.iter()
        if child.attrib.get("displayed") != "false"
        and child.attrib.get("visible") != "false"
        and child.attrib.get("text", "").strip()
    ]


def _android_single_activity_card_container(element: ElementTree.Element) -> bool:
    values = _android_descendant_texts(element)
    return (
        any(value in ACTIVITY_CATEGORY_TEXTS[1:] for value in values)
        and all(values.count(marker) == 1 for marker in ACTIVITY_CARD_MARKERS)
    )


def _android_card_context_values(values: list[str]) -> list[str]:
    return [
        value
        for value in values
        if value not in ACTIVITY_CATEGORY_TEXTS
        and value not in ACTIVITY_CARD_MARKERS
        and not _looks_like_android_metric_value(value)
        and any("\u4e00" <= character <= "\u9fff" for character in value)
    ]


def _looks_like_android_metric_value(value: str) -> bool:
    metric_characters = set("0123456789. -—约小时天晚公里kmKM场")
    return bool(value) and all(character in metric_characters for character in value)


def _extract_activity_card_texts_from_plain_source(page_source: str) -> list[str]:
    return [
        line.strip()
        for line in page_source.splitlines()
        if _looks_like_activity_card_text(line)
    ]


def _looks_like_activity_card_text(text: str) -> bool:
    if not text:
        return False
    if text.startswith("总里程"):
        return False
    if any(nav_text == text for nav_text in ACTIVITY_CATEGORY_TEXTS):
        return False
    if not all(marker in text for marker in ACTIVITY_CARD_MARKERS):
        return False
    return text.count("总里程") == 1


def _looks_like_activity_category_tag_text(text: str) -> bool:
    return any(text.startswith(category) for category in ACTIVITY_CATEGORY_TEXTS if category != "全部活动")


def _activity_card_matches_category(text: str, category_name: str) -> bool:
    if _looks_like_activity_category_tag_text(text):
        return text.startswith(category_name)
    return category_name in text


def _activity_search_visible(page_source: str) -> bool:
    return "请输入内容" in page_source and "搜索" in page_source


def _tap_activity_search_entry_by_coordinate(driver: WebDriver, page_source: str = "") -> bool:
    try:
        for x, y in _android_activity_search_entry_points(page_source):
            driver.execute_script("mobile: tap", {"x": x, "y": y})
            if _wait_until(lambda: _activity_search_visible(_safe_page_source(driver)), timeout=0.8):
                return True
        rect = driver.get_window_rect()
        capabilities = getattr(driver, "capabilities", {}) or {}
        platform = str(capabilities.get("platformName", "")).lower()
        ratios = (
            [(0.926, 0.059), (0.92, 0.06), (0.844, 0.122), (0.84, 0.12), (0.85, 0.125)]
            if platform == "android"
            else [(0.925, 0.103), (0.91, 0.10)]
        )
        for x_ratio, y_ratio in ratios:
            driver.execute_script(
                "mobile: tap",
                {"x": int(rect["width"] * x_ratio), "y": int(rect["height"] * y_ratio)},
            )
            if _wait_until(lambda: _activity_search_visible(_safe_page_source(driver)), timeout=0.8):
                return True
        return False
    except (AttributeError, KeyError, TypeError, WebDriverException):
        return False


def _android_activity_search_entry_points(page_source: str) -> list[tuple[int, int]]:
    if not page_source:
        return []
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []

    root_width = int(root.attrib.get("width", "0") or 0)
    root_height = int(root.attrib.get("height", "0") or 0)
    candidates: list[tuple[int, int, int]] = []

    def has_svg_descendant(element: ElementTree.Element) -> bool:
        return any(
            (child.attrib.get("class") or child.tag) == "com.horcrux.svg.SvgView"
            for child in element.iter()
        )

    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if (element.attrib.get("class") or element.tag) != "android.view.ViewGroup" or not has_svg_descendant(element):
            continue
        rect = _bounds_rect_from_attrs(element.attrib)
        if rect is None:
            continue
        x, y, width, height = rect
        if width < 48 or width > 180 or height < 48 or height > 150:
            continue
        if root_width and x < int(root_width * 0.70):
            continue
        if root_height and y > int(root_height * 0.16):
            continue
        candidates.append((width * height, x + width // 2, y + height // 2))

    points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for _, x, y in sorted(candidates):
        point = (x, y)
        if point in seen:
            continue
        points.append(point)
        seen.add(point)
    return points


def _find_activity_search_input(driver: WebDriver, timeout: int = 10):
    end_at = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < end_at:
        for xpath in ACTIVITY_SEARCH_INPUT_XPATHS:
            try:
                return driver.find_element(AppiumBy.XPATH, xpath)
            except (NoSuchElementException, WebDriverException) as error:
                last_error = error
                continue
        time.sleep(0.2)
    raise AssertionError("Unable to locate the activity search input") from last_error


def _replace_text(element, value: str) -> None:
    element.click()
    try:
        element.clear()
    except WebDriverException:
        pass
    element.send_keys(value)


def _hide_keyboard(driver: WebDriver) -> None:
    for kwargs in [
        {},
        {"key_name": "Done"},
        {"key_name": "Return"},
        {"strategy": "pressKey", "key_name": "Done"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            return
        except WebDriverException:
            continue
    for text in ["完成", "收起键盘", "确定"]:
        if tap_text_if_present(driver, text, timeout=1):
            return
    try:
        rect = driver.get_window_rect()
        driver.execute_script("mobile: tap", {"x": int(rect["width"] * 0.9), "y": int(rect["height"] * 0.18)})
    except WebDriverException:
        pass


def _tap_activity_search_submit(driver: WebDriver) -> bool:
    for text in ACTIVITY_SEARCH_SUBMIT_TEXTS:
        if tap_text_if_present(driver, text, timeout=1):
            return True
    if _tap_activity_keyboard_search(driver):
        return True
    if tap_by_coordinate_ratios(driver, [(0.86, 0.103), (0.84, 0.10)]):
        return True
    try:
        driver.execute_script("mobile: tap", {"x": 346, "y": 92})
        return True
    except WebDriverException:
        return False


def _tap_activity_keyboard_search(driver: WebDriver) -> bool:
    for kwargs in [
        {"key_name": "Search"},
        {"key_name": "Return"},
        {"strategy": "pressKey", "key_name": "Search"},
    ]:
        try:
            driver.hide_keyboard(**kwargs)
            return True
        except WebDriverException:
            continue
    return False


def _tap_confirm_signup(driver: WebDriver) -> bool:
    for text in ACTIVITY_SIGNUP_ACTION_TEXTS:
        if tap_text_if_present(driver, text, timeout=2):
            return True
    return tap_by_coordinate_ratios(driver, [(0.78, 0.955), (0.82, 0.94), (0.74, 0.93)])


def _tap_signup_consent(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "同意并继续", timeout=1):
        return True
    return tap_by_coordinate_ratios(driver, [(0.73, 0.955), (0.75, 0.94), (0.68, 0.95)])


def _tap_submit_activity_order(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "提交订单", timeout=2):
        return True
    return tap_by_coordinate_ratios(driver, [(0.78, 0.955), (0.78, 0.93), (0.73, 0.94)])


def _tap_me_tab(driver: WebDriver) -> bool:
    if tap_accessibility_id_or_text_if_present(driver, "bottom-nav-me", "我的", timeout=2):
        return True
    return tap_by_coordinate_ratios(driver, [(0.88, 0.93), (0.90, 0.94)])


def _tap_my_activity_entry(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "我的活动", timeout=2):
        return True
    return tap_by_coordinate_ratios(driver, [(0.50, 0.31), (0.25, 0.31)])


def _tap_my_activity_signup_tab(driver: WebDriver) -> bool:
    if tap_text_if_present(driver, "报名", timeout=2):
        return True
    return tap_by_coordinate_ratios(driver, [(0.40, 0.17), (0.43, 0.15)])


def _tap_my_activity_reaction_tab(driver: WebDriver, tab_name: str) -> bool:
    if tab_name not in {"点赞", "收藏"}:
        raise ValueError(f"Unsupported My Activity reaction tab: {tab_name}")
    if tap_text_if_present(driver, tab_name, timeout=2):
        return True
    ratios = [(0.40, 0.17), (0.43, 0.15)] if tab_name == "点赞" else [(0.62, 0.17), (0.62, 0.15)]
    return tap_by_coordinate_ratios(driver, ratios)


def _fill_signup_text_field_by_placeholder(driver: WebDriver, placeholder: str, value: str) -> bool:
    for xpath in [
        f'//XCUIElementTypeTextField[@value="{placeholder}" or @name="{placeholder}" or @label="{placeholder}"]',
        f'//XCUIElementTypeTextView[@value="{placeholder}" or @name="{placeholder}" or @label="{placeholder}"]',
        f'//*[contains(@name, "{placeholder}") or contains(@label, "{placeholder}") or contains(@value, "{placeholder}")]/following::XCUIElementTypeTextField[1]',
        f'//*[contains(@name, "{placeholder}") or contains(@label, "{placeholder}") or contains(@value, "{placeholder}")]/following::XCUIElementTypeTextView[1]',
        f'//android.widget.EditText[@hint="{placeholder}" or @text="{placeholder}"]',
    ]:
        try:
            _replace_text(driver.find_element(AppiumBy.XPATH, xpath), value)
            _hide_keyboard(driver)
            return True
        except (NoSuchElementException, WebDriverException):
            continue
    return False


def _select_signup_certificate_type(driver: WebDriver, certificate_type: str) -> bool:
    if parse_activity_signup_snapshot(_safe_page_source(driver)).certificate_type == certificate_type:
        return True

    if not tap_text_if_present(driver, "请选择证件类型", timeout=1):
        for xpath in [
            '//*[contains(@name, "请选择证件类型") or contains(@label, "请选择证件类型") or contains(@value, "请选择证件类型")]',
        ]:
            try:
                driver.find_element(AppiumBy.XPATH, xpath).click()
                break
            except (NoSuchElementException, WebDriverException):
                continue
        else:
            if not tap_by_coordinate_ratios(driver, [(0.50, 0.65), (0.80, 0.65)]):
                return False

    for text in [certificate_type, "居民身份证", "中国居民身份证"]:
        if tap_text_if_present(driver, text, timeout=2):
            return _wait_until(
                lambda: parse_activity_signup_snapshot(_safe_page_source(driver)).certificate_type == certificate_type,
                timeout=3,
            )
    return False


def _tap_activity_category(driver: WebDriver, category_name: str) -> bool:
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "right"})
    except WebDriverException:
        pass
    if tap_text_if_present(driver, category_name, timeout=1):
        return True
    try:
        driver.execute_script("mobile: scroll", {"direction": "left"})
    except WebDriverException:
        pass
    return tap_text_if_present(driver, category_name, timeout=1)


def _tap_first_activity_card(driver: WebDriver, page_source: str, verify_open=None, timeout: float = 1.2) -> bool:
    for tap_points in _activity_card_tap_point_groups(page_source):
        if _tap_activity_card_points(driver, tap_points, verify_open=verify_open, timeout=timeout):
            return True
    fallback_ratios = (
        [(0.50, 0.58), (0.50, 0.68), (0.50, 0.48)]
        if _is_ios_driver(driver)
        else [(0.50, 0.28), (0.50, 0.34), (0.50, 0.22)]
    )
    for ratio in fallback_ratios:
        if not tap_by_coordinate_ratios(driver, [ratio]):
            continue
        if verify_open is None or _wait_until(verify_open, timeout=timeout):
            return True
    return False


def _tap_activity_card_points(driver: WebDriver, tap_points: list[tuple[int, int]], verify_open=None, timeout: float = 1.2) -> bool:
    for x, y in tap_points:
        try:
            driver.execute_script("mobile: tap", {"x": x, "y": y})
            if verify_open is None or _wait_until(verify_open, timeout=timeout):
                return True
        except WebDriverException:
            continue
    return False


def _activity_card_tap_points(page_source: str) -> list[tuple[int, int]]:
    return [point for group in _activity_card_tap_point_groups(page_source) for point in group]


def _activity_card_tap_point_groups(page_source: str) -> list[list[tuple[int, int]]]:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []

    rects: list[tuple[int, int, int, int]] = []
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        text = (
            element.attrib.get("name", "")
            or element.attrib.get("label", "")
            or element.attrib.get("value", "")
            or element.attrib.get("text", "")
        ).strip()
        if not _looks_like_activity_card_text(text):
            continue
        rect = _rect_from_attrs(element.attrib)
        if rect is None:
            continue
        x, y, width, height = rect
        if width < 180 or height < 120:
            continue
        rects.append(rect)
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if not _android_single_activity_card_container(element):
            continue
        rect = _bounds_rect_from_attrs(element.attrib)
        if rect is None:
            continue
        x, y, width, height = rect
        if width < 180 or height < 120:
            continue
        rects.append(rect)

    groups: list[list[tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    prefer_card_text_area = any(element.tag.startswith("XCUIElementType") for element in root.iter())
    for x, y, width, height in sorted(set(rects), key=lambda item: (item[1], item[0])):
        x_point = x + max(1, width // 2)
        if prefer_card_text_area:
            y_candidates = [
                y + min(max(160, int(height * 0.72)), height - 20),
                y + min(max(200, int(height * 0.88)), height - 20),
            ]
        else:
            y_candidates = [
                y + min(max(48, height // 3), height - 20),
                y + min(max(72, height // 2), height - 20),
            ]
        group: list[tuple[int, int]] = []
        for y_point in y_candidates:
            point = (x_point, y_point)
            if point in seen:
                continue
            group.append(point)
            seen.add(point)
        if group:
            groups.append(group)
    return groups


def _activity_signup_action_available(page_source: str) -> bool:
    return not activity_signup_unavailable(page_source) and any(text in page_source for text in ACTIVITY_SIGNUP_ACTION_TEXTS)


def _wait_for_activity_detail_signup_state(driver: WebDriver, timeout: float = 4) -> str:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        page_source = _safe_page_source(driver)
        if _activity_signup_action_available(page_source):
            return "available"
        if activity_signup_unavailable(page_source):
            return "unavailable"
        if activity_signup_is_visible(page_source):
            return "signup"
        if activity_detail_is_visible(page_source) and not _android_activity_detail_loading_shell_visible(page_source):
            return "unknown"
        time.sleep(0.2)
    return "unknown"


def _return_to_activity_feed(driver: WebDriver) -> None:
    try:
        driver.back()
    except WebDriverException:
        return
    if _wait_until(lambda: not activity_detail_is_visible(_safe_page_source(driver)), timeout=3):
        return
    if _is_ios_driver(driver) and tap_by_coordinate_ratios(driver, [(0.07, 0.10), (0.08, 0.11)]):
        _wait_until(lambda: not activity_detail_is_visible(_safe_page_source(driver)), timeout=3)


def _activity_ready_id_present(driver: WebDriver) -> bool:
    for accessibility_id in ACTIVITY_READY_IDS:
        try:
            driver.find_element("accessibility id", accessibility_id)
            return True
        except Exception:
            continue
    return False


def _activity_ready_text_present(page_source: str) -> bool:
    return any(text in page_source for text in ACTIVITY_READY_TEXTS) and any(
        text in page_source for text in ["首页", "笔记"]
    )


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


def _extract_activity_detail_title(page_source: str, visible_texts: list[str]) -> str | None:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        root = None

    if root is not None:
        candidates: list[tuple[int, str]] = []
        for element in root.iter():
            if element.attrib.get("visible") == "false":
                continue
            raw_text = (
                element.attrib.get("name", "")
                or element.attrib.get("label", "")
                or element.attrib.get("value", "")
            )
            text = " ".join(raw_text.split())
            rect = _rect_from_attrs(element.attrib)
            if rect is None:
                continue
            _, y, width, _ = rect
            if 170 <= y <= 330 and width >= 120 and _looks_like_activity_detail_title(text):
                candidates.append((y, text))
        if candidates:
            return sorted(candidates)[0][1]

    for text in visible_texts:
        if _looks_like_activity_detail_title(text):
            return text
    return None


def _looks_like_activity_detail_title(text: str) -> bool:
    if len(text) < 4:
        return False
    if any(marker in text for marker in ["省·", "总里程", "路线说明", "活动评论", "报名费用"]):
        return False
    if text in set(ACTIVITY_CATEGORY_TEXTS) | {"ROUTE", "COMMENTS", "活动概览", "路线主理人"}:
        return False
    return True


def _first_text_containing(texts: list[str], keyword: str) -> str | None:
    return next((text for text in texts if keyword in text), None)


def _extract_signup_meeting_location(joined_text: str) -> str | None:
    match = re.search(r"集合地点\s+(.+?)(?:\s+报名截止|\s+活动名额|\s+服务配置|$)", joined_text)
    return match.group(1).strip() if match else None


def _extract_signup_input_value_by_placeholder(page_source: str, placeholder: str) -> str | None:
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return None
    for element in root.iter():
        if element.attrib.get("visible") == "false" or element.attrib.get("displayed") == "false":
            continue
        if element.attrib.get("placeholderValue") != placeholder and element.attrib.get("hint") != placeholder:
            continue
        value = " ".join((element.attrib.get("value", "") or element.attrib.get("text", "")).split())
        if not value or value == placeholder:
            return None
        return value
    return None


def _extract_signup_field_value(joined_text: str, label: str, stop_labels: list[str]) -> str | None:
    stop_pattern = "|".join(re.escape(stop_label) for stop_label in stop_labels)
    match = re.search(rf"{re.escape(label)}\s+(.+?)(?:\s+(?:{stop_pattern})|$)", joined_text)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith("请输入") or value.startswith("请选择"):
        return None
    return value or None


def _extract_signup_certificate_type(joined_text: str) -> str | None:
    value = _extract_signup_field_value(joined_text, "证件类型", ["证件号码"])
    if value is None:
        return None
    if "身份证" in value:
        return "身份证"
    return value


def _extract_activity_publisher(joined_text: str) -> str | None:
    marker = " 路线主理人"
    if marker not in joined_text:
        return None
    before_marker = joined_text.split(marker, 1)[0].split()
    return before_marker[-1] if before_marker else None


def _me_page_visible(page_source: str) -> bool:
    if "手机号登录" in page_source or "密码登录" in page_source:
        return False
    return "我的" in page_source and any(text in page_source for text in ["编辑资料", "设置", "我的活动", "草稿箱"])


def _my_activity_page_visible(page_source: str) -> bool:
    return "我的活动" in page_source and any(text in page_source for text in ["发布", "报名", "点赞", "收藏"])


def _activity_detail_hero_visible(page_source: str) -> bool:
    return "activity-route-detail-v3-hero-carousel" in page_source or (
        activity_detail_is_visible(page_source) and "XCUIElementTypeImage" in page_source
    )


def _rect_from_attrs(attrs: dict[str, str]) -> tuple[int, int, int, int] | None:
    try:
        x = int(float(attrs.get("x", "0")))
        y = int(float(attrs.get("y", "0")))
        width = int(float(attrs.get("width", "0")))
        height = int(float(attrs.get("height", "0")))
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return (x, y, width, height)


def _bounds_rect_from_attrs(attrs: dict[str, str]) -> tuple[int, int, int, int] | None:
    match = re.fullmatch(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", attrs.get("bounds", ""))
    if not match:
        return None
    x1, y1, x2, y2 = [int(value) for value in match.groups()]
    width = x2 - x1
    height = y2 - y1
    if width <= 0 or height <= 0:
        return None
    return (x1, y1, width, height)


def _safe_page_source(driver: WebDriver) -> str:
    try:
        return driver.page_source
    except WebDriverException:
        return ""


def _is_ios_driver(driver: WebDriver) -> bool:
    platform_name = (getattr(driver, "capabilities", {}) or {}).get("platformName", "")
    return str(platform_name).lower() == "ios"


def _wait_until(predicate, timeout: int = 10) -> bool:
    end_at = time.monotonic() + timeout
    while time.monotonic() < end_at:
        if predicate():
            return True
        time.sleep(0.2)
    return False
