"""Test-only callback from the rental ALIPAY Postman collection.

No credentials or order IDs are loaded from Postman globals. Call after the UI
payment step, with the current run's business order and observed App API origin.
Business readers normalize their own schema to BusinessOrder; rental is provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class PaymentMockError(RuntimeError):
    """Sanitized error; do not include response bodies, tokens or request headers."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class TestOrderContext:
    __test__ = False
    run_id: str
    business_order_id: str
    owner_id: str
    payable_amount: str
    observed_app_api_origin: str
    environment_evidence: str


@dataclass(frozen=True)
class BusinessOrder:
    id: str
    owner_id: str
    payable_amount: str
    payment_order_id: str | None
    payment_status: str
    allows_mock_payment: bool


def _amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise PaymentMockError("Missing or invalid payable amount") from None
    if not result.is_finite() or result <= 0:
        raise PaymentMockError("Mock requires a positive payable amount")
    return result


class PaymentMockClient:
    """Single callback attempt, then payment and business-state confirmation.

    read_business_order receives this client and the scoped business ID and must
    return a fresh BusinessOrder using authenticated business APIs. It must not
    return expected values or use a stale snapshot. There is no automatic /pay,
    create-payment, callback retry, deployment setting change, or live CLI.
    """

    def __init__(self, base_url, token, *, transport=None, clock=time.monotonic,
                 sleep=time.sleep, request_timeout=10):
        # Exact origin allowlist; no env label, substring or arbitrary URL override.
        if base_url != "https://dev-api.velowind.com":
            raise PaymentMockError("Mock callback only supports the dev-api test origin")
        if not token or not token.strip():
            raise PaymentMockError("Authenticated order-query token required")
        if not 0 < request_timeout <= 30:
            raise PaymentMockError("Invalid request timeout")
        self.base_url, self._token = base_url, token
        self._transport = transport or self._http
        self._clock, self._sleep = clock, sleep
        self._request_timeout = request_timeout
        self._attempted = set()

    def _http(self, method, path, *, form=None):
        headers = {"Accept": "application/json"}
        data = None
        if form is None:
            headers["Authorization"] = f"Bearer {self._token}"
        else:
            # Collection callback is noauth + x-www-form-urlencoded, not JSON.
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urlencode(form).encode("utf-8")
        request = Request(self.base_url + path, headers=headers, data=data, method=method)
        try:
            with build_opener(_NoRedirect()).open(request, timeout=self._request_timeout) as response:
                payload = response.read(1024 * 1024 + 1)
        except HTTPError as error:
            raise PaymentMockError(f"Payment API HTTP {error.code}") from None
        except (URLError, TimeoutError, OSError):
            raise PaymentMockError("Payment API transport failure; query state before retrying") from None
        if len(payload) > 1024 * 1024:
            raise PaymentMockError("Payment API response too large")
        if form is not None:
            # Callback may return channel acknowledgement text. Never equate it
            # with success: fresh authenticated payment/business queries decide.
            return None
        try:
            envelope = json.loads(payload)
        except (ValueError, UnicodeError):
            raise PaymentMockError("Invalid payment API JSON") from None
        if (not isinstance(envelope, dict) or type(envelope.get("code")) is not int
                or envelope["code"] != 0 or not isinstance(envelope.get("data"), dict)):
            raise PaymentMockError("Payment API business query failed")
        return envelope["data"]

    def get(self, path):
        if not path.startswith("/api/v1/mobile/") or any(x in path for x in ("?", "#", "..")):
            raise PaymentMockError("Invalid business-query path")
        return self._transport("GET", path)

    def _validate_business(self, context, order, payment_id=None):
        if (order.id != context.business_order_id or order.owner_id != context.owner_id
                or _amount(order.payable_amount) != _amount(context.payable_amount)):
            raise PaymentMockError("Business order identity, ownership or amount mismatch")
        if not order.payment_order_id:
            raise PaymentMockError("No bound paymentOrderId; complete normal payment preparation first")
        if order.payment_status != "SUCCEEDED" and order.allows_mock_payment is not True:
            raise PaymentMockError("Business order is not in a payable state")
        if payment_id and order.payment_order_id != payment_id:
            raise PaymentMockError("Business order payment binding changed")

    def _payment(self, payment_id, context):
        payment = self.get("/api/v1/mobile/pay/payment-orders/" + quote(payment_id, safe=""))
        if payment.get("paymentOrderId") != payment_id:
            raise PaymentMockError("Queried payment ID mismatch")
        if _amount(payment.get("payableAmount")) != _amount(context.payable_amount):
            raise PaymentMockError("Payment amount differs from this run's order")
        if payment.get("status") not in {"PENDING", "PAYING", "SUCCEEDED"}:
            raise PaymentMockError("Payment state is not eligible for mock success")
        # This collection covers direct ALIPAY, not arbitrary provider routes.
        if (payment.get("paymentMethod") != "ALIPAY" or payment.get("providerRoute") != "DIRECT"
                or payment.get("paymentChannel") != "THIRD_PARTY"):
            raise PaymentMockError("Only DIRECT ALIPAY is supported by this collection adapter")
        return payment

    def complete_success(self, context, read_business_order, *, timeout=30, interval=1):
        if (not context.run_id.strip() or not context.business_order_id.strip()
                or not context.owner_id.strip() or not context.environment_evidence.strip()
                or context.observed_app_api_origin != self.base_url):
            raise PaymentMockError("Current-run order and matching observed App environment evidence required")
        if not 0 < interval <= timeout <= 60:
            raise PaymentMockError("Invalid status polling limits")
        order = read_business_order(self, context.business_order_id)
        self._validate_business(context, order)
        payment_id = order.payment_order_id
        payment = self._payment(payment_id, context)
        if payment["status"] != "SUCCEEDED":
            # Once attempted, never resubmit in this client, including after a
            # timeout; a later invocation can still query an already-successful ID.
            if payment_id in self._attempted:
                raise PaymentMockError("Callback already attempted; reconcile payment state before proceeding")
            self._attempted.add(payment_id)
            try:
                self._transport("POST", "/api/v1/pay/callbacks/mock", form={
                    "paymentOrderId": payment_id, "trade_status": "TRADE_SUCCESS"})
            except PaymentMockError:
                # Ambiguous callback response: query actual state, never resend.
                pass
        deadline = self._clock() + timeout
        while True:
            payment = self._payment(payment_id, context)
            order = read_business_order(self, context.business_order_id)
            self._validate_business(context, order, payment_id)
            if payment["status"] == order.payment_status == "SUCCEEDED":
                return {"run_id": context.run_id, "business_order_id": order.id,
                        "payment_order_id": payment_id, "payment_status": "SUCCEEDED",
                        "business_payment_status": order.payment_status}
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise PaymentMockError("Payment/business success not confirmed; callback not resent")
            self._sleep(min(interval, remaining))


def read_rental_order(client, business_order_id):
    """Actual rental collection fields; activity enrollment needs its own mapper."""
    data = client.get("/api/v1/mobile/rental/orders/" + quote(business_order_id, safe=""))
    if data.get("id") is None or data.get("userId") is None:
        raise PaymentMockError("Rental identity/ownership fields missing")
    return BusinessOrder(str(data["id"]), str(data["userId"]), data.get("payAmount"),
                         data.get("paymentOrderId"), data.get("paymentStatus"),
                         data.get("status") in {"CREATED", "WAIT_DEPOSIT", "WAIT_PAY"})


def read_activity_enrollment(client, business_order_id):
    """Fresh enrollment + cashier binding for full-amount MAIN ALIPAY orders.

    Uses operatorUserId for the payer, never the participant's display name.
    Staged balances are intentionally rejected until their phase mapping exists.
    """
    base = "/api/v1/mobile/activity/enrollments/" + quote(business_order_id, safe="")
    detail, cashier = client.get(base), client.get(base + "/cashier")
    if (str(detail.get("enrollmentId")) != business_order_id
            or str(cashier.get("enrollmentId")) != business_order_id
            or not detail.get("operatorUserId")):
        raise PaymentMockError("Enrollment identity/ownership missing or mismatched")
    if cashier.get("phase") != "MAIN" or cashier.get("paymentMode") != "FULL_AMOUNT":
        raise PaymentMockError("Only full-amount MAIN enrollment payment is mapped")
    payment_id = detail.get("paymentOrderId")
    if not payment_id or payment_id != cashier.get("paymentOrderId"):
        raise PaymentMockError("Enrollment/cashier payment binding missing or changed")
    if cashier.get("selectedPaymentMethod") != "ALIPAY":
        raise PaymentMockError("Enrollment cashier has not selected ALIPAY")
    if detail.get("paymentStatus") != cashier.get("paymentStatus"):
        raise PaymentMockError("Enrollment/cashier payment states differ")
    return BusinessOrder(business_order_id, str(detail["operatorUserId"]),
                         cashier.get("payableAmount"), payment_id, detail.get("paymentStatus"),
                         detail.get("enrollmentStatus") in {"PENDING_PAYMENT", "WAITING_PAYMENT"})
