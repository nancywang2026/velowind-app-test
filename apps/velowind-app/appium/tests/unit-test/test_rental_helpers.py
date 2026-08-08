import pytest

from velowind_appium.modules import rental_orders
from velowind_appium.modules import rental_home_entry
from velowind_appium.modules import rental_order_confirm
from velowind_appium.modules import rental_store
from velowind_appium.modules import rental_payment_center
from velowind_appium.modules import rental_vehicle_list
from velowind_appium.modules.rental_common import visible_text_hit_points, visible_text_hit_points_containing


def test_extract_rental_order_summary_from_ios_source():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="订单编号" />
      <XCUIElementTypeStaticText name="RC202607190001" />
      <XCUIElementTypeStaticText name="下单时间" />
      <XCUIElementTypeStaticText name="2026-07-19 10:31" />
      <XCUIElementTypeStaticText name="取车时间" />
      <XCUIElementTypeStaticText name="2026-07-20 09:00" />
      <XCUIElementTypeStaticText name="还车时间" />
      <XCUIElementTypeStaticText name="2026-07-21 09:00" />
      <XCUIElementTypeStaticText name="支付未完成" />
      <XCUIElementTypeStaticText name="可重新发起支付" />
      <XCUIElementTypeStaticText name="剩余支付时间 14:59" />
    </AppiumAUT>
    """

    summary = rental_orders.extract_rental_order_summary(page_source)

    assert summary.order_number == "RC202607190001"
    assert summary.created_at == "2026-07-19 10:31"
    assert summary.pickup_time == "2026-07-20 09:00"
    assert summary.return_time == "2026-07-21 09:00"
    assert summary.payment_incomplete is True
    assert summary.repay_available is True
    assert summary.remaining_payment_time == "14:59"


def test_extract_rental_order_summary_from_android_text_nodes():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="订单编号：RC202607190002" displayed="true" />
      <android.widget.TextView text="下单时间：2026-07-19 10:45" displayed="true" />
      <android.widget.TextView text="取车时间：2026-07-20 10:00" displayed="true" />
      <android.widget.TextView text="还车时间：2026-07-21 10:00" displayed="true" />
      <android.widget.TextView text="支付未完成" displayed="true" />
      <android.widget.TextView text="可重新发起支付" displayed="true" />
      <android.widget.TextView text="剩余支付时间 09:31" displayed="true" />
    </hierarchy>
    """

    summary = rental_orders.extract_rental_order_summary(page_source)

    assert summary.order_number == "RC202607190002"
    assert summary.created_at == "2026-07-19 10:45"
    assert summary.pickup_time == "2026-07-20 10:00"
    assert summary.return_time == "2026-07-21 10:00"
    assert summary.payment_incomplete is True
    assert summary.repay_available is True
    assert summary.remaining_payment_time == "09:31"


def test_read_latest_rental_order_summary_uses_current_complete_source_before_wait(monkeypatch):
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="订单编号：RC202607190004" />
      <XCUIElementTypeStaticText name="下单时间：2026-07-19 11:45" />
      <XCUIElementTypeStaticText name="取车时间：2026-07-20 10:00" />
      <XCUIElementTypeStaticText name="还车时间：2026-07-21 10:00" />
      <XCUIElementTypeStaticText name="支付未完成" />
      <XCUIElementTypeStaticText name="可重新发起支付" />
      <XCUIElementTypeStaticText name="剩余支付时间 09:31" />
    </AppiumAUT>
    """
    waits = []

    monkeypatch.setattr(rental_orders, "safe_page_source", lambda driver: page_source)
    monkeypatch.setattr(rental_orders, "wait_for_my_rental_page", lambda driver, timeout: waits.append(timeout))

    summary = rental_orders.read_latest_rental_order_summary(object(), timeout=20)

    assert summary.is_complete() is True
    assert waits == []


def test_submit_rental_order_uses_remaining_timeout_for_payment_wait(monkeypatch):
    waits = []

    monkeypatch.setattr(rental_order_confirm, "wait_for_rental_order_confirm_page", lambda driver, timeout: None)
    monkeypatch.setattr(
        rental_order_confirm,
        "tap_first_available",
        lambda driver, accessibility_ids, texts, timeout: True,
    )
    monkeypatch.setattr(
        rental_order_confirm,
        "wait_for_rental_payment_center_page",
        lambda driver, timeout: waits.append(timeout),
    )

    rental_order_confirm.submit_rental_order(object(), timeout=25)

    assert waits and waits[0] > 20


def test_confirm_payment_prefers_ios_coordinate_before_locator_scan(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(rental_payment_center, "wait_for_rental_payment_center_page", lambda driver, timeout: None)
    monkeypatch.setattr(
        rental_payment_center,
        "tap_by_coordinate_ratios",
        lambda driver, ratios: events.append(("coordinate", tuple(ratios))) or True,
    )
    monkeypatch.setattr(
        rental_payment_center,
        "tap_first_available",
        lambda *args, **kwargs: events.append(("locator",)) or True,
    )
    monkeypatch.setattr(rental_payment_center, "wait_until_source_contains", lambda driver, texts, timeout: True)
    monkeypatch.setattr(rental_payment_center, "dismiss_pending_payment_dialog_if_present", lambda driver, timeout: True)
    monkeypatch.setattr(rental_payment_center, "wait_for_my_rental_page", lambda driver, timeout: None)

    rental_payment_center.confirm_payment_then_think_again(FakeDriver(), timeout=5)

    assert events == [
        ("coordinate", ((0.50, 0.93), (0.50, 0.91))),
    ]


def test_dismiss_payment_dialog_prefers_visible_think_again_hit_point(monkeypatch):
    events = []

    class FakeDriver:
        pass

    sources = iter(["确认发起支付 再想想", "我的租车"])
    monkeypatch.setattr(rental_payment_center, "safe_page_source", lambda driver: next(sources))
    monkeypatch.setattr(
        rental_payment_center,
        "tap_visible_text_hit_point",
        lambda driver, texts, timeout: events.append(("hit-point", tuple(texts))) or True,
    )
    monkeypatch.setattr(
        rental_payment_center,
        "tap_first_available",
        lambda *args, **kwargs: events.append(("locator",)) or True,
    )
    monkeypatch.setattr(
        rental_payment_center,
        "tap_by_coordinate_ratios",
        lambda *args, **kwargs: events.append(("coordinate",)) or True,
    )
    monkeypatch.setattr(rental_payment_center.time, "sleep", lambda seconds: None)

    assert rental_payment_center.dismiss_pending_payment_dialog_if_present(FakeDriver(), timeout=2) is True
    assert events == [
        ("hit-point", tuple(rental_payment_center.THINK_AGAIN_TEXTS)),
    ]


def test_dismiss_payment_dialog_prefers_ios_dialog_coordinate(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

    monkeypatch.setattr(rental_payment_center, "safe_page_source", lambda driver: "确认发起支付 再想想")
    monkeypatch.setattr(
        rental_payment_center,
        "tap_by_coordinate_ratios",
        lambda driver, ratios: events.append(("coordinate", tuple(ratios))) or True,
    )
    monkeypatch.setattr(
        rental_payment_center,
        "tap_visible_text_hit_point",
        lambda *args, **kwargs: events.append(("hit-point",)) or True,
    )

    assert rental_payment_center.dismiss_pending_payment_dialog_if_present(FakeDriver(), timeout=2) is True
    assert events == [
        ("coordinate", ((0.32, 0.56), (0.35, 0.58), (0.32, 0.62))),
    ]


def test_summary_is_complete_requires_all_order_fields():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="订单编号：RC202607190003" displayed="true" />
      <android.widget.TextView text="支付未完成" displayed="true" />
      <android.widget.TextView text="可重新发起支付" displayed="true" />
    </hierarchy>
    """

    summary = rental_orders.extract_rental_order_summary(page_source)

    assert summary.is_complete() is False


def test_visible_text_hit_points_uses_ios_container_center_for_matching_label():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="车辆详情 立即预定" label="车辆详情 立即预定" visible="true" x="17" y="704" width="368" height="75">
        <XCUIElementTypeOther name="车辆详情" label="车辆详情" visible="true" x="30" y="717" width="168" height="49">
          <XCUIElementTypeStaticText value="车辆详情" name="车辆详情" label="车辆详情" visible="true" x="83" y="731" width="62" height="21" />
        </XCUIElementTypeOther>
        <XCUIElementTypeOther name="立即预定" label="立即预定" visible="true" x="206" y="717" width="166" height="49" />
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    assert visible_text_hit_points(page_source, ["车辆详情"]) == [(114, 741)]


def test_visible_text_hit_points_uses_android_bounds_center_for_matching_text():
    page_source = """
    <hierarchy>
      <android.view.View text="车辆详情" displayed="true" bounds="[30,717][198,766]" />
      <android.widget.TextView text="车辆详情" displayed="true" bounds="[83,731][145,752]" />
      <android.view.View text="车辆详情" displayed="false" bounds="[10,10][20,20]" />
    </hierarchy>
    """

    assert visible_text_hit_points(page_source, ["车辆详情"]) == [(114, 741)]


def test_visible_text_hit_points_containing_matches_ios_label_suffix():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="去支付¥3670.00" label="去支付¥3670.00" visible="true" x="0" y="768" width="402" height="106">
        <XCUIElementTypeStaticText value="去支付¥3670.00" name="去支付¥3670.00" label="去支付¥3670.00" visible="true" x="145" y="792" width="112" height="21" />
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    assert (201, 821) in visible_text_hit_points_containing(page_source, ["去支付"])


class _FakeRentalDriver:
    def __init__(self, page_source: str):
        self.page_source = page_source


def test_rental_home_visible_rejects_post_detail_overlay():
    driver = _FakeRentalDriver(
        '推荐 post-home-feed-category-pager post-detail-banner-pager 活动 消息 我的'
    )

    assert rental_home_entry._home_visible(driver) is False


def test_rental_home_visible_rejects_ios_my_activity_page_with_cached_home_text():
    driver = _FakeRentalDriver(
        """
        <AppiumAUT>
          <XCUIElementTypeOther name="全国 推荐 骑行 活动 消息 我的 我的活动 报名 点赞 收藏 发布"
            label="全国 推荐 骑行 活动 消息 我的 我的活动 报名 点赞 收藏 发布"
            visible="true" x="0" y="0" width="402" height="874">
            <XCUIElementTypeStaticText name="我的活动" label="我的活动" value="我的活动"
              visible="true" x="162" y="78" width="78" height="26" />
            <XCUIElementTypeOther name="全国 推荐 笔记" label="全国 推荐 笔记"
              visible="false" x="0" y="0" width="402" height="874" />
          </XCUIElementTypeOther>
        </AppiumAUT>
        """
    )

    assert rental_home_entry._home_visible(driver) is False


def test_rental_home_visible_allows_home_rental_entry_text():
    driver = _FakeRentalDriver("首页 全国 推荐 活动 消息 我的 租车 floating-rent-entry")

    assert rental_home_entry._home_visible(driver) is True


def test_rental_entry_ids_include_android_floating_rent_entry():
    assert "floating-rent-entry" in rental_home_entry.RENTAL_ENTRY_IDS


def test_wait_for_store_selected_checks_final_state_after_timeout(monkeypatch):
    driver = _FakeRentalDriver("租车 服务门店 上海市 立即选车")

    ticks = iter([0.0, 6.0])
    monkeypatch.setattr(rental_store.time, "monotonic", lambda: next(ticks))

    assert rental_store._wait_for_store_selected(driver, timeout=5) is True


def test_choose_first_store_opens_store_picker_before_tapping_first_store(monkeypatch):
    driver = _FakeRentalDriver("租车 服务门店 上海市 请选择服务门店 立即选车")
    events = []

    monkeypatch.setattr(rental_store, "wait_for_rental_store_page", lambda received, timeout=15: "store")
    monkeypatch.setattr(rental_store, "tap_by_coordinate_ratios", lambda *args, **kwargs: False)
    monkeypatch.setattr(rental_store.time, "sleep", lambda seconds: None)

    now = [0.0]

    def fake_monotonic():
        now[0] += 0.1
        return now[0]

    monkeypatch.setattr(rental_store.time, "monotonic", fake_monotonic)

    def fake_tap_text_containing(received, keywords, timeout=2):
        events.append(("tap-containing", tuple(keywords)))
        if keywords == ["请选择服务门店"]:
            driver.page_source = "租车 服务门店 上海市 请选择服务门店 虹桥店 吴中路1366号 立即选车"
            return True
        return False

    def fake_tap_first_available(received, accessibility_ids, texts, timeout=2):
        events.append(("tap-first", tuple(texts)))
        if "虹桥店" in texts and "虹桥店" in driver.page_source:
            driver.page_source = "租车 服务门店 上海市 虹桥店 立即选车"
            return True
        return False

    monkeypatch.setattr(rental_store, "tap_by_text_containing", fake_tap_text_containing)
    monkeypatch.setattr(rental_store, "tap_first_available", fake_tap_first_available)

    rental_store.choose_first_store(driver, timeout=2)

    assert events == [
        ("tap-containing", ("请选择服务门店",)),
        ("tap-first", ("第一个门店", "虹桥店")),
    ]


def test_visible_vehicle_detail_bookable_ignores_hidden_unavailable_vehicle_list():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther
        name="选择车辆 文化生活服务车 不可预定 车辆详情 立即预定 车辆详情 文化生活服务车 基本信息 日租参考 ￥1800.00 /天 立即预定"
        label="选择车辆 文化生活服务车 不可预定 车辆详情 立即预定 车辆详情 文化生活服务车 基本信息 日租参考 ￥1800.00 /天 立即预定"
        visible="true" x="0" y="0" width="402" height="874">
      <XCUIElementTypeOther
        name="选择车辆 文化生活服务车 不可预定 车辆详情 立即预定"
        label="选择车辆 文化生活服务车 不可预定 车辆详情 立即预定"
        visible="false" x="0" y="0" width="402" height="874" />
      <XCUIElementTypeOther
        name="车辆详情 文化生活服务车 基本信息 日租参考 ￥1800.00 /天 立即预定"
        label="车辆详情 文化生活服务车 基本信息 日租参考 ￥1800.00 /天 立即预定"
        visible="true" x="0" y="0" width="402" height="874">
        <XCUIElementTypeStaticText name="车辆详情" label="车辆详情" value="车辆详情"
          visible="true" x="162" y="78" width="78" height="26" />
        <XCUIElementTypeStaticText name="立即预定" label="立即预定" value="立即预定"
          visible="true" x="305" y="792" width="61" height="21" />
      </XCUIElementTypeOther>
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    assert rental_vehicle_list._visible_vehicle_detail_bookable(page_source) is True


def test_bookable_vehicle_detail_hit_points_prefer_visible_bookable_row():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="选择车辆" label="选择车辆" visible="true" x="0" y="100" width="402" height="600">
        <XCUIElementTypeOther name="文化生活服务车 不可预定 车辆详情" label="文化生活服务车 不可预定 车辆详情"
          visible="true" x="0" y="140" width="402" height="160">
          <XCUIElementTypeStaticText name="车辆详情" label="车辆详情" value="车辆详情"
            visible="true" x="250" y="250" width="80" height="30" />
        </XCUIElementTypeOther>
        <XCUIElementTypeOther name="文化生活服务车 可预定 车辆详情" label="文化生活服务车 可预定 车辆详情"
          visible="true" x="0" y="320" width="402" height="160">
          <XCUIElementTypeStaticText name="车辆详情" label="车辆详情" value="车辆详情"
            visible="true" x="250" y="430" width="80" height="30" />
        </XCUIElementTypeOther>
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    assert rental_vehicle_list._bookable_vehicle_detail_hit_points(page_source) == [(290, 445)]


def test_bookable_vehicle_detail_hit_points_accepts_ios_immediate_booking_label():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="选择车辆" label="选择车辆" visible="true" x="0" y="100" width="402" height="600">
        <XCUIElementTypeOther name="文化生活服务车 不可预定 车辆详情" label="文化生活服务车 不可预定 车辆详情"
          visible="true" x="0" y="140" width="402" height="160">
          <XCUIElementTypeStaticText name="车辆详情" label="车辆详情" value="车辆详情"
            visible="true" x="250" y="250" width="80" height="30" />
        </XCUIElementTypeOther>
        <XCUIElementTypeOther name="文化生活服务车 立即预定 车辆详情" label="文化生活服务车 立即预定 车辆详情"
          visible="true" x="0" y="320" width="402" height="160">
          <XCUIElementTypeStaticText name="车辆详情" label="车辆详情" value="车辆详情"
            visible="true" x="250" y="430" width="80" height="30" />
        </XCUIElementTypeOther>
      </XCUIElementTypeOther>
    </AppiumAUT>
    """

    assert rental_vehicle_list._bookable_vehicle_detail_hit_points(page_source) == [(290, 445)]


def test_open_rental_from_home_tries_floating_truck_coordinate_fallback(monkeypatch):
    driver = _FakeRentalDriver("首页 全国 推荐 活动 消息 我的")
    events = []

    monkeypatch.setattr(rental_home_entry, "_activate_configured_app_if_needed", lambda driver: None)
    monkeypatch.setattr(rental_home_entry, "_recover_home_before_opening_rental", lambda driver: None)
    monkeypatch.setattr(rental_home_entry, "_rental_store_visible", lambda driver: False)
    monkeypatch.setattr(rental_home_entry, "tap_first_available", lambda *args, **kwargs: False)
    monkeypatch.setattr(rental_home_entry, "tap_by_text_containing", lambda *args, **kwargs: False)
    monkeypatch.setattr(rental_home_entry, "_wait_for_store_after_tap", lambda driver: False)
    monkeypatch.setattr(
        rental_home_entry,
        "tap_by_coordinate_ratios",
        lambda driver, ratios: events.append(tuple(ratios)) or True,
    )
    ticks = iter([0.0, 0.2, 0.4, 0.6, 0.8, 1.1, 1.4, 1.7, 2.0])
    monkeypatch.setattr(rental_home_entry.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(rental_home_entry.time, "sleep", lambda seconds: None)

    with pytest.raises(AssertionError):
        rental_home_entry.open_rental_from_home(driver, timeout=1)

    assert events
