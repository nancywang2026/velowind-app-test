from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from xml.etree import ElementTree

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    extract_visible_texts,
    safe_page_source,
    visible_text_hit_points,
    wait_for_rental_page,
)
from velowind_appium.reporting import attach_text


MY_RENTAL_PAGE_IDS = ["my-rental-page", "rental-orders-page", "my-rent-car-page"]
MY_RENTAL_PAGE_TEXTS = ["我的租车", "订单编号", "支付未完成", "可重新发起支付"]
ORDER_NUMBER_LABELS = ["订单编号", "订单号"]
CREATED_AT_LABELS = ["下单时间"]
PICKUP_TIME_LABELS = ["取车时间", "驱车时间"]
RETURN_TIME_LABELS = ["还车时间"]
TIME_PATTERN = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}")
ORDER_NUMBER_PATTERN = re.compile(r"(?:订单编号|订单号)[:：\s]*([A-Za-z0-9_-]{6,})")
REMAINING_TIME_PATTERN = re.compile(r"剩余支付时间[:：\s]*(\d{1,2}:\d{2}(?::\d{2})?)")


@dataclass(frozen=True)
class RentalOrderSummary:
    order_number: str | None
    created_at: str | None
    pickup_time: str | None
    return_time: str | None
    payment_incomplete: bool
    repay_available: bool
    remaining_payment_time: str | None

    def is_complete(self, *, require_remaining_payment_time: bool = True) -> bool:
        return all(
            [
                self.order_number,
                self.created_at,
                self.pickup_time,
                self.return_time,
                self.payment_incomplete,
                self.repay_available,
                self.remaining_payment_time if require_remaining_payment_time else True,
            ]
        )


def wait_for_my_rental_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=MY_RENTAL_PAGE_IDS,
        texts=MY_RENTAL_PAGE_TEXTS,
        timeout=timeout,
    )


def read_latest_rental_order_summary(
    driver: WebDriver, timeout: int = 20, *, expected_order_number: str | None = None
) -> RentalOrderSummary:
    end_at = time.monotonic() + timeout
    last_summary = RentalOrderSummary(None, None, None, None, False, False, None)
    detail_in_front = False
    is_android = str((getattr(driver, "capabilities", {}) or {}).get("platformName", "")).lower() == "android"
    while time.monotonic() < end_at:
        source = safe_page_source(driver)
        detail_in_front = is_android and _android_order_detail_before_list(source)
        last_summary = extract_rental_order_summary(source, expected_order_number=expected_order_number)
        if not detail_in_front and last_summary.is_complete(require_remaining_payment_time=not is_android):
            return last_summary
        remaining_timeout = max(0.5, end_at - time.monotonic())
        wait_for_my_rental_page(driver, timeout=remaining_timeout)
        source = safe_page_source(driver)
        detail_in_front = is_android and _android_order_detail_before_list(source)
        last_summary = extract_rental_order_summary(source, expected_order_number=expected_order_number)
        if not detail_in_front and last_summary.is_complete(require_remaining_payment_time=not is_android):
            return last_summary
        time.sleep(0.4)
    raise AssertionError(f"Latest rental order summary is incomplete or behind order detail (detail_in_front={detail_in_front}): {last_summary}")


def _android_order_detail_before_list(page_source: str) -> bool:
    detail_title = page_source.find('text="订单详情"')
    rental_title = page_source.find('text="我的租车"')
    return detail_title >= 0 and rental_title > detail_title


def extract_rental_order_summary(page_source: str, *, expected_order_number: str | None = None) -> RentalOrderSummary:
    if expected_order_number:
        page_source = _matching_android_order_card(page_source, expected_order_number)
    texts = extract_visible_texts(page_source)
    joined_text = " ".join(texts)
    time_values = _extract_time_values(texts)

    return RentalOrderSummary(
        order_number=expected_order_number if expected_order_number and expected_order_number in texts else _extract_order_number(texts, joined_text),
        created_at=_extract_labeled_time(texts, CREATED_AT_LABELS) or _time_at(time_values, 0),
        pickup_time=_extract_labeled_time(texts, PICKUP_TIME_LABELS) or _time_at(time_values, 1),
        return_time=_extract_labeled_time(texts, RETURN_TIME_LABELS) or _time_at(time_values, 2),
        payment_incomplete="支付未完成" in joined_text or "待支付" in joined_text,
        repay_available="可重新发起支付" in joined_text or "重新支付" in joined_text or "继续支付" in joined_text,
        remaining_payment_time=_extract_remaining_payment_time(texts, joined_text),
    )


def _matching_android_order_card(page_source: str, order_number: str) -> str:
    if "<hierarchy" not in page_source:
        return page_source
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return ""
    parents = {child: parent for parent in root.iter() for child in parent}
    for element in root.iter():
        if element.attrib.get("text") != order_number:
            continue
        card = parents.get(element)
        if card is None:
            break
        card = parents.get(card, card)
        return ElementTree.tostring(card, encoding="unicode")
    return ""


def _cleanup_order_card(page_source: str, order_number: str) -> str:
    """Find one order's card; never fall back to actions on the whole page."""
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return ""
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter():
        values = [node.get(key, "").strip() for key in ("text", "name", "label", "value")]
        matches = [ORDER_NUMBER_PATTERN.fullmatch(value) for value in values]
        if order_number not in values and not any(match and match.group(1) == order_number for match in matches):
            continue
        card = node
        candidate = ""
        while card is not None:
            if card.get("visible") == "false" or card.get("displayed") == "false":
                return ""
            source = ElementTree.tostring(card, encoding="unicode")
            texts = extract_visible_texts(source)
            text = " ".join(texts)
            numbers = set(re.findall(r"\b(?:RO|RC)[A-Za-z0-9_-]{6,}\b", text))
            if numbers - {order_number} or "我的租车" in texts or "订单详情" in texts:
                break
            if TIME_PATTERN.search(text) and any(
                status in text for status in ("待支付", "支付未完成", "已取消", "订单已关闭")
            ) and any(label in text for label in ("取消订单", "已取消", "订单已关闭")):
                # A hidden ancestor makes even displayed descendants unsafe to tap.
                ancestor = card
                while ancestor is not None:
                    if ancestor.get("visible") == "false" or ancestor.get("displayed") == "false":
                        return ""
                    ancestor = parents.get(ancestor)
                candidate = source
            card = parents.get(card)
        if candidate:
            return candidate
    return ""


def _order_card_cancelled(card_source: str) -> bool:
    texts = extract_visible_texts(card_source)
    text = " ".join(texts)
    return bool(card_source) and "已取消" in text and not any(
        label in text for label in ("待支付", "支付未完成", "取消订单", "去支付")
    )


def _cancel_confirmation_points(page_source: str) -> list[tuple[int, int]]:
    texts = extract_visible_texts(page_source)
    if "确认取消当前租车订单吗？" in texts:
        return visible_text_hit_points(page_source, ["确认取消"])
    try:
        root = ElementTree.fromstring(page_source)
    except ElementTree.ParseError:
        return []
    for node in root.iter():
        if node.tag != "XCUIElementTypeAlert" and node.get("resource-id") != "android:id/parentPanel":
            continue
        source = ElementTree.tostring(node, encoding="unicode")
        if not re.search(r"取消.{0,8}订单|订单.{0,8}取消", " ".join(extract_visible_texts(source))):
            continue
        return visible_text_hit_points(source, ["确认取消", "确定取消", "确定", "确认"])
    return []


def cancel_rental_order(driver: WebDriver, order_number: str, timeout: int = 20) -> dict[str, str]:
    """Cancel only the submitted unpaid order and verify its card changed state."""
    result = {"order_number": order_number, "status": "pending"}
    try:
        if not re.fullmatch(r"(?:RO|RC)[A-Za-z0-9_-]{6,}", order_number or ""):
            raise AssertionError("A valid submitted rental order number is required for cleanup")
        source = safe_page_source(driver)
        if _android_order_detail_before_list(source):
            driver.back()
            wait_for_my_rental_page(driver, timeout=5)
            source = safe_page_source(driver)
        if _android_order_detail_before_list(source):
            raise AssertionError("Rental order list is still behind an order detail page")
        card = _cleanup_order_card(source, order_number)
        if not _order_card_cancelled(card):
            texts = " ".join(extract_visible_texts(card))
            if not any(status in texts for status in ("待支付", "支付未完成")):
                raise AssertionError(f"Cannot find unpaid rental order card for cleanup: {order_number}")
            points = visible_text_hit_points(card, ["取消订单"])
            if not points:
                raise AssertionError(f"Cancel button missing on rental order: {order_number}")
            x, y = points[0]
            driver.execute_script("mobile: tap", {"x": x, "y": y})
            end_at = time.monotonic() + timeout
            confirmed = False
            while time.monotonic() < end_at:
                source = safe_page_source(driver)
                card = _cleanup_order_card(source, order_number)
                if not _android_order_detail_before_list(source) and _order_card_cancelled(card):
                    break
                points = _cancel_confirmation_points(source)
                if points and not confirmed:
                    x, y = points[0]
                    driver.execute_script("mobile: tap", {"x": x, "y": y})
                    confirmed = True
                time.sleep(0.4)
            else:
                raise AssertionError(f"Rental order cancellation was not confirmed: {order_number}")
        result["status"] = "cancelled"
        attach_text("rental-order-cleanup-result", json.dumps(result, ensure_ascii=False))
        return result
    except Exception as error:
        result["error"] = str(error)
        attach_text("rental-order-cleanup-pending", json.dumps(result, ensure_ascii=False))
        raise


def _extract_order_number(texts: list[str], joined_text: str) -> str | None:
    for text in texts:
        match = ORDER_NUMBER_PATTERN.search(text)
        if match:
            return match.group(1)
    for index, text in enumerate(texts):
        if any(label == text or label in text for label in ORDER_NUMBER_LABELS):
            next_text = _next_meaningful_text(texts, index)
            if next_text and not any(label in next_text for label in ORDER_NUMBER_LABELS):
                return next_text.strip(":： ")
    match = ORDER_NUMBER_PATTERN.search(joined_text)
    return match.group(1) if match else None


def _extract_labeled_time(texts: list[str], labels: list[str]) -> str | None:
    for text in texts:
        if any(label in text for label in labels):
            match = TIME_PATTERN.search(text)
            if match:
                return match.group(0)
    for index, text in enumerate(texts):
        if any(label == text or label in text for label in labels):
            next_text = _next_meaningful_text(texts, index)
            if not next_text:
                continue
            match = TIME_PATTERN.search(next_text)
            if match:
                return match.group(0)
    return None


def _extract_remaining_payment_time(texts: list[str], joined_text: str) -> str | None:
    for text in texts:
        match = REMAINING_TIME_PATTERN.search(text)
        if match:
            return match.group(1)
    match = REMAINING_TIME_PATTERN.search(joined_text)
    if match:
        return match.group(1)
    for index, text in enumerate(texts):
        if "剩余支付时间" not in text:
            continue
        next_text = _next_meaningful_text(texts, index)
        if next_text:
            time_match = re.search(r"\d{1,2}:\d{2}(?::\d{2})?", next_text)
            if time_match:
                return time_match.group(0)
    return None


def _extract_time_values(texts: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for match in TIME_PATTERN.finditer(text):
            value = match.group(0)
            if value in seen:
                continue
            values.append(value)
            seen.add(value)
    return values


def _next_meaningful_text(texts: list[str], index: int) -> str | None:
    for next_text in texts[index + 1 :]:
        if next_text and next_text not in {"：", ":"}:
            return next_text
    return None


def _time_at(values: list[str], index: int) -> str | None:
    return values[index] if len(values) > index else None
