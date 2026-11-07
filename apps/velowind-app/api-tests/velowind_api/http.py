"""Strict JSON transport. Never retries mutations; records redacted requests and responses."""
import json
import allure
from .redaction import Redactor
from .console import log
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ApiError(RuntimeError):
    pass


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("base_url must be a credential-free HTTP(S) URL")
    return url.rstrip("/")


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpClient:
    def __init__(self, base_url, timeout=15, interval=0, journal=None, opener=None):
        self.base_url = validate_url(base_url)
        self.timeout, self.interval = timeout, interval
        self.journal = journal if journal is not None else []
        self.opener = opener or build_opener(NoRedirects())
        self.redactor = Redactor()

    def request(self, method, path, *, token=None, body=None, params=None, request_id=None):
        with allure.step(f"{method} {path}"):
            return self._request(method, path, token=token, body=body, params=params, request_id=request_id)

    def _capture_response(self, response, status):
        raw = response.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
            is_json = True
        except ValueError:
            payload, is_json = text, False
        captured = self.redactor.clean({"status_code": status,
            "headers": dict(getattr(response, "headers", {}) or {}),
            "body": payload, "body_format": "json" if is_json else "text"})
        return captured, payload, is_json

    def _request(self, method, path, *, token=None, body=None, params=None, request_id=None):
        if not path.startswith("/api/") or "?" in path or "#" in path:
            raise ValueError("API path must be an absolute /api/ path without query")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if method != "GET":
            request_id = request_id or str(uuid.uuid4())
            headers["X-Request-Id"] = request_id
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode()
        query = "?" + urlencode(params) if params else ""
        req = Request(self.base_url + path + query, data=data, headers=headers, method=method)
        entry = {"method": method, "path": path, "request_id": request_id, "status": "started"}
        entry["start"] = int(time.time() * 1000)
        self.redactor.remember({"token": token, "headers": headers, "body": body, "query": params})
        safe_query = "?" + urlencode(self.redactor.clean(params)) if params else ""
        entry["request"] = self.redactor.clean({"method": method, "url": self.base_url + path + safe_query,
            "headers": headers, "query": params or {}, "body": body})
        entry["response"] = {"status_code": None, "headers": {}, "body": None,
                             "unavailable_reason": "No HTTP response received"}
        self.journal.append(entry)
        started = time.monotonic()
        log("HTTP", f"开始 {method} {self.redactor.text(path)}")
        try:
            if self.interval:
                time.sleep(self.interval)
            with self.opener.open(req, timeout=self.timeout) as response:
                entry["http_status"] = response.status
                captured, envelope, is_json = self._capture_response(response, response.status)
                entry["response"] = captured
                if not 200 <= response.status < 300:
                    raise ApiError(f"HTTP {response.status}")
                if not is_json:
                    raise ValueError("Non-JSON response")
            if not isinstance(envelope, dict) or type(envelope.get("code")) is not int:
                raise ApiError("Invalid API envelope/code")
            entry["business_code"] = envelope["code"]
            if envelope["code"] != 0:
                raise ApiError(f"Business error code={envelope['code']}")
            if not isinstance(envelope.get("data"), dict):
                raise ApiError("Missing/invalid response data")
            entry["status"] = "passed"
            return envelope["data"]
        except HTTPError as exc:
            entry["http_status"] = exc.code
            try:
                entry["response"], _, _ = self._capture_response(exc, exc.code)
            except (OSError, ValueError):
                entry["response"] = {"status_code": exc.code, "headers": self.redactor.clean(dict(exc.headers or {})),
                                     "body": None, "unavailable_reason": "HTTP error body could not be read"}
            finally:
                exc.close()
            entry["status"] = "failed"
            error_body = entry["response"].get("body")
            details = ""
            if isinstance(error_body, dict) and type(error_body.get("code")) is int:
                entry["business_code"] = error_body["code"]
                details = f"; business_code={error_body['code']}"
                key = error_body.get("messageKey")
                if isinstance(key, str) and key.replace(".", "").replace("_", "").replace("-", "").isalnum():
                    details += f"; messageKey={key}"
            raise ApiError(f"HTTP {exc.code}{details}; inspect server with request_id={request_id}") from None
        except (URLError, OSError, TimeoutError, ValueError):
            entry["status"] = "unknown" if method != "GET" else "failed"
            raise ApiError("Transport/JSON failure; mutation outcome may be unknown; no retry") from None
        except ApiError:
            entry["status"] = "failed"
            raise
        finally:
            entry["stop"] = int(time.time() * 1000)
            entry["duration_seconds"] = round(time.monotonic() - started, 3)
            log("HTTP", f"{method} {self.redactor.text(path)} -> {entry['status']} "
                f"HTTP={entry.get('http_status', '-')} code={entry.get('business_code', '-')} "
                f"({entry['duration_seconds']:.2f}s)")
            for kind in ("request", "response"):
                allure.attach(json.dumps(entry[kind], ensure_ascii=False, indent=2),
                              kind, allure.attachment_type.JSON)
