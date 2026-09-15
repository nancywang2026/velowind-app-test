"""Title-scoped XML selection and authenticated note deletion.

Set VW_NOTE_CLEANUP_MODE=api to use this for post-publication cleanup;
unset it or set ui to retain the original UI workflow. Bulk cleanup is unchanged.
Credentials come from app_config.login_username/login_password (existing YAML
login settings or VW_LOGIN_USERNAME/VW_LOGIN_PASSWORD overrides). The configured
account must own the published note. API errors propagate without a UI fallback.
"""
import json
import re
import uuid
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoteCleanupApiError(RuntimeError):
    """Sanitized API failure; never includes credentials or response bodies."""


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


def _request_data(method, url, *, body=None, token=None):
    headers = {"Accept": "application/json", "X-Request-Id": str(uuid.uuid4())}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with build_opener(_NoRedirect()).open(request, timeout=20) as response:
            result = json.load(response)
    except HTTPError as error:
        raise NoteCleanupApiError(f"Note cleanup {method} failed: HTTP {error.code}") from None
    except (URLError, OSError, ValueError):
        raise NoteCleanupApiError(f"Note cleanup {method} failed: network or invalid JSON response") from None
    if not isinstance(result, dict) or result.get("code") != 0 or not isinstance(result.get("data"), dict):
        raise NoteCleanupApiError(f"Note cleanup {method} failed: unsuccessful API response")
    return result["data"]


def delete_note_via_api(post_id: str, phone: str, password: str) -> None:
    if not re.fullmatch(r"pst-[0-9a-fA-F]{32}", post_id):
        raise ValueError("Invalid note postId")
    if not phone or not password:
        raise NoteCleanupApiError("API cleanup requires configured login username and password")
    base = "https://dev-api.velowind.com/api/v1/mobile"
    login = _request_data("POST", base + "/auth/login/phone/password",
                          body={"phone": str(phone), "password": password})
    token = login.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        raise NoteCleanupApiError("Login response is missing accessToken")
    deleted = _request_data("DELETE", base + "/posts/" + post_id, token=token)
    if deleted.get("postId") != post_id or deleted.get("deleted") is not True:
        raise NoteCleanupApiError("API did not confirm deletion of the selected note")
