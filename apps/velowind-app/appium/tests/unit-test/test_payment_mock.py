from dataclasses import replace
from urllib.parse import parse_qs
import pytest

from velowind_appium.payment_mock import (
    BusinessOrder, PaymentMockClient, PaymentMockError, TestOrderContext, read_rental_order,
)


def context(**changes):
    return replace(TestOrderContext("run-unique", "42", "user-A", "10.05",
                   "https://dev-api.velowind.com", "observed App request origin"), **changes)


class Server:
    def __init__(self):
        self.calls = []
        self.paid = False
        self.callback_error = False
        self.callback_commits = True
        self.business_sync = True
        self.payment_changes = {}
        self.order_changes = {}

    def transport(self, method, path, *, form=None):
        self.calls.append((method, path, form))
        if method == "POST":
            if self.callback_commits:
                self.paid = True
            if self.callback_error:
                raise PaymentMockError("response lost")
            return None
        return {"paymentOrderId": "pay-current", "payableAmount": "10.05",
                "paymentChannel": "THIRD_PARTY", "paymentMethod": "ALIPAY",
                "providerRoute": "DIRECT", "status": "SUCCEEDED" if self.paid else "PENDING",
                **self.payment_changes}

    def read_order(self, client, order_id):
        return replace(BusinessOrder("42", "user-A", "10.05", "pay-current",
                       "SUCCEEDED" if self.paid and self.business_sync else "PENDING", True),
                       **self.order_changes)

    @property
    def writes(self):
        return [call for call in self.calls if call[0] == "POST"]


def client(server):
    ticks = [0]
    def sleep(seconds):
        ticks[0] += seconds
    return PaymentMockClient("https://dev-api.velowind.com", "test-only-token",
                             transport=server.transport, clock=lambda: ticks[0], sleep=sleep)


def test_callback_uses_bound_order_then_confirms_both_states():
    server = Server()
    result = client(server).complete_success(context(), server.read_order)
    assert result["payment_order_id"] == "pay-current"
    assert result["business_order_id"] == "42"
    assert server.writes == [("POST", "/api/v1/pay/callbacks/mock", {
        "paymentOrderId": "pay-current", "trade_status": "TRADE_SUCCESS"})]


@pytest.mark.parametrize("origin", ["https://api.velowind.com", "https://dev-api.velowind.com.evil.test",
                                      "http://dev-api.velowind.com", "https://dev-api.velowind.com/path"])
def test_only_exact_test_origin_allowed(origin):
    with pytest.raises(PaymentMockError):
        PaymentMockClient(origin, "test-only-token")


@pytest.mark.parametrize("changes", [{"observed_app_api_origin": "https://api.velowind.com"},
                                     {"environment_evidence": ""}, {"run_id": ""}])
def test_environment_and_run_checks_happen_before_any_request(changes):
    server = Server()
    with pytest.raises(PaymentMockError):
        client(server).complete_success(context(**changes), server.read_order)
    assert server.calls == []


@pytest.mark.parametrize("changes", [{"id": "old-order"}, {"owner_id": "other"},
        {"payable_amount": "20"}, {"payment_order_id": None}, {"allows_mock_payment": False}])
def test_rejects_wrong_stale_or_unpayable_business_order(changes):
    server = Server()
    server.order_changes = changes
    with pytest.raises(PaymentMockError):
        client(server).complete_success(context(), server.read_order)
    assert server.calls == []


@pytest.mark.parametrize("changes", [{"paymentOrderId": "old-payment"}, {"payableAmount": "20"},
        {"payableAmount": "NaN"}, {"status": "CLOSED"}, {"providerRoute": "MALLBOOK"},
        {"paymentMethod": "WECHAT"}, {"paymentChannel": "BALANCE"}])
def test_payment_contract_mismatch_never_sends_callback(changes):
    server = Server()
    server.payment_changes = changes
    with pytest.raises(PaymentMockError):
        client(server).complete_success(context(), server.read_order)
    assert not server.writes


def test_already_successful_order_is_queried_without_replay():
    server = Server()
    server.paid = True
    assert client(server).complete_success(context(), server.read_order)["payment_status"] == "SUCCEEDED"
    assert not server.writes


def test_lost_callback_response_reconciles_instead_of_resending():
    server = Server()
    server.callback_error = True
    assert client(server).complete_success(context(), server.read_order)["payment_status"] == "SUCCEEDED"
    assert len(server.writes) == 1


def test_callback_ack_is_not_business_success_and_is_not_retried():
    server = Server()
    server.business_sync = False
    api = client(server)
    with pytest.raises(PaymentMockError, match="not confirmed"):
        api.complete_success(context(), server.read_order, timeout=2)
    assert len(server.writes) == 1


def test_unknown_payment_outcome_does_not_resend_in_same_client():
    server = Server()
    server.callback_commits = False
    server.callback_error = True
    api = client(server)
    with pytest.raises(PaymentMockError, match="not confirmed"):
        api.complete_success(context(), server.read_order, timeout=2)
    with pytest.raises(PaymentMockError, match="already attempted"):
        api.complete_success(context(), server.read_order, timeout=2)
    assert len(server.writes) == 1


def test_rental_reader_uses_authenticated_order_detail_and_real_binding():
    paths = []
    class Reader:
        def get(self, path):
            paths.append(path)
            return {"id": 42, "userId": "user-A", "payAmount": 10.05,
                    "paymentOrderId": "bound-payment", "paymentStatus": "PENDING", "status": "WAIT_PAY"}
    order = read_rental_order(Reader(), "42")
    assert paths == ["/api/v1/mobile/rental/orders/42"]
    assert order.payment_order_id == "bound-payment"
    assert order.allows_mock_payment


def test_http_callback_is_form_encoded_noauth_and_does_not_follow_redirects(monkeypatch):
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return b"success"
    class Opener:
        def open(self, request, timeout):
            captured.append(request)
            return Response()
    def build(handler):
        assert handler.redirect_request(None, None, 302, "", {}, "https://example.com") is None
        return Opener()
    monkeypatch.setattr("velowind_appium.payment_mock.build_opener", build)
    api = PaymentMockClient("https://dev-api.velowind.com", "never-send-to-callback")
    api._http("POST", "/api/v1/pay/callbacks/mock", form={
        "paymentOrderId": "pay-current", "trade_status": "TRADE_SUCCESS"})
    request = captured[0]
    assert request.get_header("Authorization") is None
    assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert parse_qs(request.data.decode()) == {
        "paymentOrderId": ["pay-current"], "trade_status": ["TRADE_SUCCESS"]}


def test_activity_reader_uses_payer_and_actual_cashier_binding():
    from unittest.mock import Mock
    from velowind_appium.payment_mock import read_activity_enrollment
    c=Mock()
    c.get.side_effect=[{'enrollmentId':'en-current','operatorUserId':'payer','enrolleeName':'participant',
        'paymentOrderId':'payment-current','paymentStatus':'PENDING','enrollmentStatus':'PENDING_PAYMENT'},
        {'enrollmentId':'en-current','paymentOrderId':'payment-current','paymentStatus':'PENDING',
         'phase':'MAIN','paymentMode':'FULL_AMOUNT','selectedPaymentMethod':'ALIPAY','payableAmount':'10.05'}]
    order=read_activity_enrollment(c,'en-current')
    assert order.owner_id=='payer' and order.payment_order_id=='payment-current'
    assert order.payable_amount=='10.05' and order.allows_mock_payment


@pytest.mark.parametrize('change',[
    {'paymentOrderId':'stale-payment'}, {'phase':'BALANCE'}, {'selectedPaymentMethod':'WECHAT'},
    {'paymentMode':'DEPOSIT'}, {'enrollmentId':'other'}, {'paymentStatus':'SUCCEEDED'}])
def test_activity_reader_rejects_cross_binding_or_unsupported_phase(change):
    from unittest.mock import Mock
    from velowind_appium.payment_mock import read_activity_enrollment
    c=Mock()
    c.get.side_effect=[{'enrollmentId':'en-current','operatorUserId':'payer','paymentOrderId':'payment-current',
                       'paymentStatus':'PENDING','enrollmentStatus':'PENDING_PAYMENT'},
        {'enrollmentId':'en-current','paymentOrderId':'payment-current','paymentStatus':'PENDING',
         'phase':'MAIN','paymentMode':'FULL_AMOUNT','selectedPaymentMethod':'ALIPAY','payableAmount':'10.05',**change}]
    with pytest.raises(PaymentMockError):read_activity_enrollment(c,'en-current')
