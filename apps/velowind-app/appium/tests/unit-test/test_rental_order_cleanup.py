import pytest

from velowind_appium.modules import rental_orders


def card(order_number, status="待支付", x=100):
    action = (
        f'<android.widget.TextView text="取消订单" bounds="[{x},100][{x + 80},140]"/>'
        '<android.widget.TextView text="去支付"/>'
        if status == "待支付" else '<android.widget.TextView text="订单已关闭"/>'
    )
    return f'''<android.view.ViewGroup><android.view.ViewGroup>
        <android.widget.TextView text="{order_number}"/>
        <android.widget.TextView text="{status}"/>
        <android.widget.TextView text="2026-09-30 16:04"/>
        </android.view.ViewGroup>{action}</android.view.ViewGroup>'''


def page(*cards):
    return '<hierarchy><android.widget.TextView text="我的租车"/>' + ''.join(cards) + '</hierarchy>'


class Driver:
    def __init__(self, *sources):
        self.sources = iter(sources)
        self.current = ""
        self.taps = []

    @property
    def page_source(self):
        self.current = next(self.sources, self.current)
        return self.current

    def execute_script(self, command, point):
        self.taps.append((command, point))


@pytest.fixture
def attachments(monkeypatch):
    records = []
    monkeypatch.setattr(rental_orders, 'attach_text', lambda name, body: records.append((name, body)))
    monkeypatch.setattr(rental_orders.time, 'sleep', lambda seconds: None)
    return records


def test_cancels_only_target_card_and_confirms_its_final_state(attachments):
    initial = page(card('ROOTHER123', x=100), card('ROTARGET456', x=400))
    dialog = '''<hierarchy><android.widget.LinearLayout resource-id="android:id/parentPanel">
        <android.widget.TextView text="确定取消订单吗？"/>
        <android.widget.Button text="确定" bounds="[500,600][600,660]"/>
        </android.widget.LinearLayout></hierarchy>'''
    finished = page(card('ROOTHER123', x=100), card('ROTARGET456', status='已取消', x=400))
    driver = Driver(initial, dialog, finished)

    result = rental_orders.cancel_rental_order(driver, 'ROTARGET456')

    assert driver.taps == [('mobile: tap', {'x': 440, 'y': 120}), ('mobile: tap', {'x': 550, 'y': 630})]
    assert result == {'order_number': 'ROTARGET456', 'status': 'cancelled'}
    assert attachments[0][0] == 'rental-order-cleanup-result'


def test_other_cancelled_order_cannot_mask_target_cancellation_failure(monkeypatch, attachments):
    source = page(card('ROOTHER123', status='已取消'), card('ROTARGET456', x=400))
    driver = Driver(source)
    ticks = iter([0, 0, 2])
    monkeypatch.setattr(rental_orders.time, 'monotonic', lambda: next(ticks))

    with pytest.raises(AssertionError, match='cancellation was not confirmed'):
        rental_orders.cancel_rental_order(driver, 'ROTARGET456', timeout=1)

    assert len(driver.taps) == 1
    assert attachments[0][0] == 'rental-order-cleanup-pending'


def test_missing_target_never_cancels_another_order(attachments):
    driver = Driver(page(card('ROOTHER123')))

    with pytest.raises(AssertionError, match='Cannot find unpaid'):
        rental_orders.cancel_rental_order(driver, 'ROTARGET456')

    assert driver.taps == []
    assert attachments[0][0] == 'rental-order-cleanup-pending'


def test_already_cancelled_target_is_idempotent(attachments):
    driver = Driver(page(card('ROTARGET456', status='已取消')))

    assert rental_orders.cancel_rental_order(driver, 'ROTARGET456')['status'] == 'cancelled'
    assert driver.taps == []


def test_hidden_card_and_unrelated_alert_are_not_actionable():
    source = '<hierarchy><android.view.ViewGroup displayed="false">' + card('ROTARGET456') + '</android.view.ViewGroup></hierarchy>'
    assert rental_orders._cleanup_order_card(source, 'ROTARGET456') == ''
    assert rental_orders._cancel_confirmation_points('''<hierarchy>
        <android.widget.LinearLayout resource-id="android:id/parentPanel">
        <android.widget.TextView text="确认发起支付"/>
        <android.widget.Button text="确定" bounds="[500,600][600,660]"/>
        </android.widget.LinearLayout></hierarchy>''') == []


def test_recognizes_observed_rental_cancel_dialog():
    source = '''<hierarchy><android.view.ViewGroup>
        <android.widget.TextView text="取消订单"/>
        <android.widget.TextView text="确认取消当前租车订单吗？"/>
        <android.widget.TextView text="再想想" bounds="[332,1461][479,1527]"/>
        <android.widget.TextView text="确认取消" bounds="[778,1461][974,1527]"/>
        </android.view.ViewGroup></hierarchy>'''
    assert rental_orders._cancel_confirmation_points(source) == [(876, 1494)]


def test_cancelled_badge_does_not_hide_remaining_payment_controls():
    source = page('''<android.view.ViewGroup><android.view.ViewGroup>
        <android.widget.TextView text="ROTARGET456"/>
        <android.widget.TextView text="已取消"/>
        <android.widget.TextView text="2026-09-30 16:04"/>
        </android.view.ViewGroup><android.widget.TextView text="去支付"/>
        </android.view.ViewGroup>''')
    target = rental_orders._cleanup_order_card(source, 'ROTARGET456')
    assert '去支付' in target
    assert rental_orders._order_card_cancelled(target) is False
