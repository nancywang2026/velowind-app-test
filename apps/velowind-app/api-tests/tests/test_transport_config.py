import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
import pytest
from velowind_api.config import ConfigError, load_config, validate_config
from velowind_api.http import ApiError, HttpClient


class Response(io.BytesIO):
    status = 200


class Opener:
    def __init__(self, result):
        self.result, self.calls = result, []

    def open(self, request, **kwargs):
        self.calls.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return Response(self.result)


@pytest.mark.parametrize("result", [b"not-json", b'{"code":false,"data":{}}',
    b'{"code":123,"data":{}}', b'{"code":0,"data":null}',
    URLError("sensitive-detail"), HTTPError("http://localhost", 401, "secret", {}, io.BytesIO(b'{}'))], ids=["invalid-json", "bool-code", "business-error", "missing-data", "network", "http-401"])
def test_transport_failure_does_not_retry_or_leak(result):
    opener = Opener(result)
    client = HttpClient("http://localhost", opener=opener)
    with pytest.raises(ApiError) as error:
        client.request("POST", "/api/send", token="sensitive-token", body={"password": "sensitive-password"})
    assert len(opener.calls) == 1
    assert "sensitive" not in str(error.value)
    assert "sensitive" not in json.dumps(client.journal)


def test_url_and_path_boundaries():
    for url in ("ftp://host", "https://user:password@host", "https://host?token=x"):
        with pytest.raises(ValueError):
            HttpClient(url)
    with pytest.raises(ValueError):
        HttpClient("https://host").request("GET", "https://other/steal")


@pytest.mark.parametrize("field,value", [("page_size", 0), ("page_size", 51), ("page_size", 2),
    ("max_pages", True), ("http_timeout_seconds", float("nan")), ("request_interval_seconds", -1)])
def test_invalid_execution_config(config, field, value):
    config["execution"][field] = value
    with pytest.raises(ConfigError):
        validate_config(config)


def test_inconsistent_expectations(config):
    config["expected"]["unread_b"] = 9
    with pytest.raises(ConfigError):
        validate_config(config)


def test_duplicate_accounts(config):
    config["accounts"]["c"] = config["accounts"]["b"]
    with pytest.raises(ConfigError):
        validate_config(config)


def test_postman_disabled_and_os_override(tmp_path):
    data = Path(__file__).parent / "fixtures/scenario.json"
    environment = json.loads((Path(__file__).parent / "fixtures/environment.json").read_text())
    environment["values"][0]["enabled"] = False
    target = tmp_path / "environment.json"
    target.write_text(json.dumps(environment))
    with pytest.raises(ConfigError, match="base_url"):
        load_config(data, target, environ={})
    loaded = load_config(data, target, environ={"base_url": "https://test.invalid"})
    assert loaded["base_url"] == "https://test.invalid"


def test_redirection_is_not_followed():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    calls = []

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/api/other")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with pytest.raises(ApiError, match="302"):
            HttpClient(f"http://127.0.0.1:{server.server_port}").request("GET", "/api/test", token="private")
        assert calls == ["/api/test"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_pinned_sorting_and_missing_flags():
    from velowind_api.checks import pinned
    with pytest.raises(AssertionError, match="sorted"):
        pinned([{"peerUserId": "x", "pinned": False}, {"peerUserId": "c", "pinned": True}], "c")
    with pytest.raises(AssertionError):
        pinned([{"peerUserId": "c", "pinned": "true"}], "c")
    pinned([{"peerUserId": "x", "pinned": True}, {"peerUserId": "c", "pinned": True}], "c")


def test_masked_credentials_are_rejected(config):
    config["accounts"]["a"]["password"] = "••••••••"
    with pytest.raises(ConfigError):
        validate_config(config)


def test_cli_missing_config_fails_before_network(tmp_path, monkeypatch):
    import sys
    from velowind_api.__main__ import main
    data = tmp_path / "invalid.json"
    data.write_text('{"base_url":"${MISSING_TEST_VARIABLE}"}')
    report = tmp_path / "report.json"
    monkeypatch.delenv("MISSING_TEST_VARIABLE", raising=False)
    monkeypatch.setattr(sys, "argv", ["velowind_api", "--data", str(data), "--check-config", "--report", str(report), "--alluredir", str(tmp_path / "allure-results")])
    assert main() == 2
    result = json.loads(report.read_text())
    assert result["status"] == "blocked" and result["requests"] == []
    assert report.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('value', ['true', 1, None])
def test_invalid_preparation_flag(config, value):
    config['preparation'] = {'mark_b_history_read': value}
    with pytest.raises(ConfigError):
        validate_config(config)
