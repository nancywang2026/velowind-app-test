from __future__ import annotations

import json
import time
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class BridgeError(RuntimeError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class MessageBridge:
    """Client for the documented test-only adapter, NOT an invented product API.

    The configured endpoint implements operation dispatch and normalizes existing
    product APIs. No implicit mutation retries or cross-host redirects.
    """

    def __init__(self, url, token, execution, run_id, case_id, variant):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise BridgeError("Invalid bridge URL; use a credential-free HTTP(S) endpoint")
        self.url, self.token, self.execution = url, token, execution
        self.identity = {"run_id": run_id, "case_id": case_id, "variant": variant}
        self.opener = build_opener(NoRedirects())

    def call(self, operation, **payload):
        request = Request(self.url, data=json.dumps({
            "protocol_version": 1, **self.identity, "operation": operation, "payload": payload,
        }).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"}, method="POST")
        try:
            with self.opener.open(request, timeout=self.execution["http_timeout_seconds"]) as response:
                body = json.load(response)
        except HTTPError as exc:
            raise BridgeError(f"Test bridge {operation} returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise BridgeError(f"Test bridge {operation} transport/JSON failure; outcome may be unknown") from None
        if not isinstance(body, dict) or body.get("ok") is not True or not isinstance(body.get("data"), dict):
            raise BridgeError(f"Invalid test bridge {operation} response")
        return body["data"]

    def wait(self, query, predicate, description):
        deadline = time.monotonic() + self.execution["business_timeout_seconds"]
        while True:
            value = query()
            if predicate(value):
                return value
            if time.monotonic() >= deadline:
                raise AssertionError(f"Business state timeout: {description}")
            time.sleep(self.execution["poll_seconds"])

    def read(self, kind, entity_id=None, **parameters):
        return self.call("read", kind=kind, entity_id=entity_id, **parameters)

    def cleanup(self):
        result = self.call("cleanup")
        if result.get("remaining_ids") != []:
            raise BridgeError("Test bridge cleanup did not confirm an empty resource registry")

    @contextmanager
    def prepared(self, **payload):
        # A timeout can occur after resources were created. Cleanup is mandatory
        # even when prepare itself does not return successfully.
        try:
            yield self.call("prepare", **payload)
        finally:
            self.cleanup()
