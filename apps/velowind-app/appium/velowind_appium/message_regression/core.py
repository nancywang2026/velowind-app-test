from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import re
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class Blocked(RuntimeError):
    """Missing execution prerequisite, never a business pass."""


class ApiFailure(RuntimeError):
    def __init__(self, status=None, code=None, message_key=None):
        self.status, self.code, self.message_key = status, code, message_key
        super().__init__(f"Business API failed: HTTP={status}, code={code}")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def identifier(value):
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise AssertionError("Missing business identifier")
    return str(value)


def segment(value):
    return quote(identifier(value), safe="")


@dataclass(frozen=True)
class Actor:
    user_id: str
    name: str
    token: str = field(repr=False)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class API:
    def __init__(self, origin, *, opener=None, timeout=15):
        if origin != "https://dev-api.velowind.com":
            raise Blocked("Message mutations require the confirmed dev-api test origin")
        self.origin, self.timeout = origin, timeout
        self.opener = opener or build_opener(NoRedirect())
        self.journal = []

    def request(self, actor, method, path, *, body=None, params=None, request_id=None):
        if not path.startswith("/api/v1/") or any(x in path for x in ("?", "#", "..")):
            raise ValueError("Invalid relative business API path")
        headers = {"Accept": "application/json"}
        if actor:
            headers["Authorization"] = f"Bearer {actor.token}"
        request_id = request_id or str(uuid.uuid4())
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", request_id):
            raise ValueError("Invalid request ID")
        if method != "GET": headers["X-Request-Id"] = request_id
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body, ensure_ascii=False).encode()
        record = {"method": method, "path": path, "request_id": request_id, "status": "started"}
        self.journal.append(record)  # No credentials, body, auth response or personal data.
        url = self.origin + path + ("?" + urlencode(params) if params else "")
        req = Request(url, headers=headers, data=payload, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000: raise ValueError("Oversized response")
                envelope = json.loads(raw)
            if not isinstance(envelope, dict) or type(envelope.get("code")) is not int:
                raise ValueError("Invalid API envelope")
            record["code"] = envelope["code"]
            if envelope["code"] != 0: raise ApiFailure(code=envelope["code"],message_key=_safe_key(envelope.get("messageKey")))
            record["status"] = "passed"
            return envelope.get("data")  # mutations may legitimately return null
        except HTTPError as exc:
            record.update(status="failed", http_status=exc.code)
            code, key = None, None
            try:
                envelope = json.loads(exc.read(65536))
                if isinstance(envelope,dict):
                    code = envelope.get("code") if type(envelope.get("code")) is int else None
                    key = _safe_key(envelope.get("messageKey"))
            except (OSError, ValueError): pass
            exc.close()
            record.update(code=code, message_key=key)
            raise ApiFailure(status=exc.code,code=code,message_key=key) from None
        except ApiFailure:
            record["status"] = "failed"
            raise
        except (OSError, URLError, ValueError, TimeoutError):
            record["status"] = "unknown" if method != "GET" else "failed"
            raise ApiFailure() from None  # Never retry a mutation.

    def login(self, phone, password, *, expected_id, name):
        data = self.request(None, "POST", "/api/v1/mobile/auth/login/phone/password",
                            body={"phone": phone, "password": password})
        require(isinstance(data, dict) and data.get("accessToken"), "Login missing access token")
        require(identifier(data.get("userId")) == str(expected_id), "Login identity mismatch")
        return Actor(str(expected_id), name, data["accessToken"])

    def login_admin(self, username, password, *, expected_id, name):
        data = self.request(None, "POST", "/api/v1/admin/auth/login",
                            body={"username": username, "password": password})
        require(isinstance(data, dict) and data.get("accessToken"), "Admin login missing access token")
        require(identifier(data.get("userId")) == str(expected_id), "Admin login identity mismatch")
        if data.get("passwordResetRequired") is not False:
            raise Blocked("Admin account requires password reset; no automatic password changes")
        actor = Actor(str(expected_id), name, data["accessToken"])
        session = self.request(actor, "GET", "/api/v1/admin/auth/session")
        require(str(session.get("userId")) == actor.user_id, "Admin session identity mismatch")
        require(bool(session.get("roles")) and session.get("passwordResetRequired") is False,
                "Admin session has no active role or requires reset")
        return actor

    def pages(self, actor, path, *, params=None, id_key, mode="page", limit=50, max_pages=40):
        """Complete bounded traversal. Duplicates/stale cursors are errors, not deduped away."""
        params = dict(params or {})
        found, seen, cursors = [], set(), set()
        for page in range(1, max_pages + 1):
            query = {**params, "pageSize": limit}
            if mode == "page": query["pageNo"] = page
            data = self.request(actor, "GET", path, params=query)
            require(isinstance(data, dict) and isinstance(data.get("items"), list), "Invalid paged response")
            for item in data["items"]:
                key = identifier(item.get(id_key))
                require(key not in seen, "Duplicate ID in paged results")
                seen.add(key); found.append(item)
            if mode == "page":
                snapshot = data.get("querySnapshot")
                if snapshot:
                    if "querySnapshot" in params:
                        require(params["querySnapshot"] == snapshot, "Notification snapshot changed while paging")
                    params["querySnapshot"] = snapshot
                total = data.get("total")
                require(type(total) is int and total >= len(found), "Invalid or changing page total")
                if len(found) == total: return found
                require(bool(data["items"]), "Empty intermediate page before total reached")
            else:
                cursor = data.get("nextCursor")
                more = data.get("hasMore")
                require(type(more) is bool, "Missing cursor hasMore")
                if not more: return found
                require(cursor and cursor not in cursors, "Missing/repeated pagination cursor")
                cursors.add(cursor); params["cursor"] = cursor
        raise AssertionError("Pagination limit reached before complete result")


def _safe_key(value):
    return value if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9._-]{1,200}",value) else None


def wait(query, predicate, *, timeout=30, interval=1, clock=time.monotonic, sleep=time.sleep):
    if not 0 < interval <= timeout <= 120: raise ValueError("Invalid polling bounds")
    end = clock() + timeout
    while True:
        value = query()
        if predicate(value): return value
        remaining = end - clock()
        if remaining <= 0: raise AssertionError("Expected business state not reached before deadline")
        sleep(min(interval, remaining))


class Resources:
    """Register compensation before a mutation, preserve body and cleanup outcomes."""
    def __init__(self):
        self.items, self.results = [], []

    def add(self, label, action, verify):
        self.items.append((label, action, verify))

    def cleanup(self):
        for label, action, verify in reversed(self.items):
            try:
                action()
                require(verify(), "Cleanup result not confirmed")
                self.results.append({"resource": label, "status": "cleaned"})
            except Exception as exc:
                self.results.append({"resource": label, "status": "cleanup-pending", "error": type(exc).__name__})
        if any(x["status"] == "cleanup-pending" for x in self.results):
            raise AssertionError("cleanup-pending: inspect resource ledger")

    @contextmanager
    def managed(self):
        try:
            yield self
        finally:
            self.cleanup()
