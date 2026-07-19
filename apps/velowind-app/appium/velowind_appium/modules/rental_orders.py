from __future__ import annotations

from dataclasses import dataclass
import re
import time

from appium.webdriver.webdriver import WebDriver

from velowind_appium.modules.rental_common import (
    extract_visible_texts,
    safe_page_source,
    wait_for_rental_page,
)


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

    def is_complete(self) -> bool:
        return all(
            [
                self.order_number,
                self.created_at,
                self.pickup_time,
                self.return_time,
                self.payment_incomplete,
                self.repay_available,
                self.remaining_payment_time,
            ]
        )


def wait_for_my_rental_page(driver: WebDriver, timeout: int = 20) -> str | None:
    return wait_for_rental_page(
        driver,
        accessibility_ids=MY_RENTAL_PAGE_IDS,
        texts=MY_RENTAL_PAGE_TEXTS,
        timeout=timeout,
    )


def read_latest_rental_order_summary(driver: WebDriver, timeout: int = 20) -> RentalOrderSummary:
    end_at = time.monotonic() + timeout
    last_summary = RentalOrderSummary(None, None, None, None, False, False, None)
    while time.monotonic() < end_at:
        wait_for_my_rental_page(driver, timeout=timeout)
        last_summary = extract_rental_order_summary(safe_page_source(driver))
        if last_summary.is_complete():
            return last_summary
        time.sleep(0.4)
    raise AssertionError(f"Latest rental order summary is incomplete: {last_summary}")


def extract_rental_order_summary(page_source: str) -> RentalOrderSummary:
    texts = extract_visible_texts(page_source)
    joined_text = " ".join(texts)
    time_values = _extract_time_values(texts)

    return RentalOrderSummary(
        order_number=_extract_order_number(texts, joined_text),
        created_at=_extract_labeled_time(texts, CREATED_AT_LABELS) or _time_at(time_values, 0),
        pickup_time=_extract_labeled_time(texts, PICKUP_TIME_LABELS) or _time_at(time_values, 1),
        return_time=_extract_labeled_time(texts, RETURN_TIME_LABELS) or _time_at(time_values, 2),
        payment_incomplete="支付未完成" in joined_text or "待支付" in joined_text,
        repay_available="可重新发起支付" in joined_text or "重新支付" in joined_text or "继续支付" in joined_text,
        remaining_payment_time=_extract_remaining_payment_time(texts, joined_text),
    )


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
