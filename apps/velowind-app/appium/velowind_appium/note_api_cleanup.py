"""Title-scoped XML selection and authenticated note deletion.

Set cleanup.note_cleanup_mode in cleanup.yaml for persistent selection.
VW_NOTE_CLEANUP_MODE=api|ui overrides that selection. Bulk cleanup is unchanged.
Credentials come from app_config.login_username/login_password (existing YAML
login settings or VW_LOGIN_USERNAME/VW_LOGIN_PASSWORD overrides). The configured
account must own the published note. API errors propagate without a UI fallback.
"""
import json
import re
import time
import uuid
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

from velowind_appium.reporting import allure, attach_text


class NoteCleanupApiError(RuntimeError):
    """Sanitized API failure; never includes credentials or response bodies."""


def api_cleanup_enabled():
    from velowind_appium.cleanup_config import note_cleanup_mode
    return note_cleanup_mode() == "api"


def remember_published_post_id(driver, source, title):
    """Capture only the current publication's uniquely named card during verification."""
    publication = getattr(driver, "_api_note_publication", None)
    if not publication or publication["published_title"] != title:
        return
    ids = note_post_ids_from_xml(source, title)
    if len(ids) == 1:
        if publication.get("post_id") not in (None, ids[0]):
            raise NoteCleanupApiError("Publication XML changed to a different postId")
        publication["post_id"] = ids[0]
        attach_text("published-note-post-id", json.dumps(publication, ensure_ascii=False, indent=2))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def note_post_ids_from_xml(source: str, title: str) -> list[str]:
    """Select exact visible card titles; preserve the complete pst- identifier."""
    from velowind_appium.modules.message_detail import _ios_note_card_title

    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return []
    normalize = lambda text: "".join(text.split())
    matched = set()

    def visit(node):
        if node.get("visible") == "false" or node.get("displayed") == "false":
            return
        for key in ("resource-id", "name", "content-desc", "testID"):
            match = re.fullmatch(
                r"(?:[^\s]+:id/)?post-home-feed-note-card-(pst-[0-9a-fA-F]{32})",
                node.get(key, ""),
            )
            if not match:
                continue
            titles = []
            ios_title = _ios_note_card_title({"type": node.tag, **node.attrib})
            if ios_title:
                titles.append(ios_title)

            def collect(child):
                if child.get("visible") == "false" or child.get("displayed") == "false":
                    return
                kind = child.get("type", child.tag)
                if kind.endswith("TextView") or kind == "XCUIElementTypeStaticText":
                    titles.append(child.get("text") or child.get("label") or child.get("name", ""))
                for descendant in child:
                    collect(descendant)
            collect(node)
            if title and any(normalize(candidate) == normalize(title) for candidate in titles):
                matched.add(match.group(1))
        for child in node:
            visit(child)
    visit(root)
    return sorted(matched)


def _redact(value, secrets=()):
    if isinstance(value, dict):
        return {key: "<redacted>" if any(part in re.sub(r"[^a-z]", "", key.lower())
                for part in ("password", "token", "authorization", "cookie", "secret"))
                else _redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "<redacted>")
    return value


def _request_data(method, url, *, body=None, token=None):
    with allure.step(f"API {method} {url}"):
        return _reported_request_data(method, url, body=body, token=token)


def _reported_request_data(method, url, *, body=None, token=None):
    headers = {"Accept": "application/json", "X-Request-Id": str(uuid.uuid4())}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    secrets = [token, (body or {}).get("password")]
    record = {"request": {"method": method, "url": url, "headers": headers, "body": body},
              "response": None}
    request = Request(url, data=payload, headers=headers, method=method)
    started = time.monotonic()

    def read_response(response, status):
        raw = response.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        record["response"] = {"status": status, "headers": dict(getattr(response, "headers", {}) or {})}
        try:
            result = json.loads(raw)
        except ValueError:
            # Arbitrary HTML/text can contain credentials: do not persist it.
            record["response"]["body"] = "<non-JSON response omitted>"
            raise ValueError("Invalid JSON") from None
        record["response"]["body"] = result
        def collect_tokens(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if "token" in key.lower() and isinstance(item, str):
                        secrets.append(item)
                    collect_tokens(item)
            elif isinstance(value, list):
                for item in value:
                    collect_tokens(item)
        collect_tokens(result)
        return result

    try:
        try:
            with build_opener(_NoRedirect()).open(request, timeout=20) as response:
                result = read_response(response, getattr(response, "status", None))
        except HTTPError as error:
            with error:
                try:
                    read_response(error, error.code)
                except (OSError, ValueError):
                    pass
            raise NoteCleanupApiError(f"Note cleanup {method} failed: HTTP {error.code}") from None
        except (URLError, OSError, ValueError):
            raise NoteCleanupApiError(f"Note cleanup {method} failed: network or invalid JSON response") from None
        if not isinstance(result, dict) or result.get("code") != 0 or not isinstance(result.get("data"), dict):
            raise NoteCleanupApiError(f"Note cleanup {method} failed: unsuccessful API response")
        record["outcome"] = "success"
        return result["data"]
    except NoteCleanupApiError as error:
        record["outcome"] = "failed"
        record["error"] = str(error)
        raise
    finally:
        record["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
        attach_text("api-call", json.dumps(_redact(record, secrets), ensure_ascii=False, indent=2))


def delete_note_via_api(post_id: str, phone: str, password: str) -> None:
    if not re.fullmatch(r"pst-[0-9a-fA-F]{32}", post_id):
        raise ValueError("Invalid note postId")
    if not phone or not password:
        raise NoteCleanupApiError("API cleanup requires configured login username and password")
    base = "https://uat-api.velowind.com/api/v1/mobile"
    login = _request_data("POST", base + "/auth/login/phone/password",
                          body={"phone": str(phone), "password": password})
    token = login.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        raise NoteCleanupApiError("Login response is missing accessToken")
    deleted = _request_data("DELETE", base + "/posts/" + post_id, token=token)
    if deleted.get("postId") != post_id or deleted.get("deleted") is not True:
        raise NoteCleanupApiError("API did not confirm deletion of the selected note")
