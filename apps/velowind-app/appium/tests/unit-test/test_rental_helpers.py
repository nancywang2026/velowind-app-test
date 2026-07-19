from velowind_appium.modules import rental_orders


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
