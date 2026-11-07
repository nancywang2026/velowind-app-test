import json
import pytest
from urllib.error import URLError
from velowind_api.http import HttpClient, ApiError
from velowind_api.scenario import new_report, step
from test_transport_config import Opener


def test_console_reports_steps_http_without_credentials(capsys):
    client = HttpClient('https://test.invalid', opener=Opener(
        b'{"code":0,"data":{"accessToken":"response-secret"}}'))
    with step(new_report(), '01 登录'):
        client.request('POST','/api/login', token='header-secret',
                       body={'phone':'13800000000','password':'password-secret'})
    output = capsys.readouterr().out
    assert '[STEP]' in output and '[PASS]' in output
    assert 'HTTP=200 code=0' in output and '/api/login' in output
    for value in ('response-secret','header-secret','13800000000','password-secret'):
        assert value not in output


def test_console_reports_network_failure(capsys):
    client = HttpClient('https://test.invalid', opener=Opener(URLError('secret-detail')))
    with pytest.raises(ApiError):
        with step(new_report(), '发送'):
            client.request('POST','/api/send')
    output = capsys.readouterr().out
    assert '[FAIL]' in output and 'unknown HTTP=-' in output
    assert 'secret-detail' not in output


def test_console_flushes_immediately(monkeypatch):
    from velowind_api.console import log
    calls = []
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: calls.append((args,kwargs)))
    log('WAIT','等待21s')
    assert calls[0][1]['flush'] is True
