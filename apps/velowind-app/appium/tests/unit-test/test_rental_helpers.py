from velowind_appium.modules import rental_orders
from velowind_appium.modules import rental_home_entry
from velowind_appium.modules.rental_common import visible_text_hit_points


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


class _FakeRentalDriver:
    def __init__(self, page_source: str):
        self.page_source = page_source


def test_rental_home_visible_rejects_post_detail_overlay():
    driver = _FakeRentalDriver(
        '推荐 post-home-feed-category-pager post-detail-banner-pager 活动 消息 我的'
    )

    assert rental_home_entry._home_visible(driver) is False


def test_rental_entry_ids_include_android_floating_rent_entry():
    assert "floating-rent-entry" in rental_home_entry.RENTAL_ENTRY_IDS
