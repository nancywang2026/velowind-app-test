import io
import json
from urllib.error import HTTPError, URLError
import pytest
from velowind_api.http import ApiError, HttpClient
from velowind_api.reporting import write_allure
from velowind_api.scenario import new_report, step
from test_transport_config import Opener


def test_request_response_attachments_are_nested_and_redacted(tmp_path):
    response = {"code":0,"data":{"accessToken":"server-secret", "userId":"user-a",
                "nested":{"refresh_token":"refresh-secret"}, "echo":"client-secret"}}
    report = new_report()
    client = HttpClient('https://test.invalid', journal=report['requests'], opener=Opener(json.dumps(response).encode()))
    with step(report, 'login'):
        returned = client.request('POST','/api/login', token='auth-secret',
                                  body={'phone':'13800000000','password':'client-secret'}, params={'pageSize':50})
    assert returned['accessToken'] == 'server-secret'
    report['status'] = 'passed'
    write_allure(report,tmp_path)
    result = json.loads(next(tmp_path.glob('*-result.json')).read_text())
    call = result['steps'][0]['steps'][0]
    assert [a['name'] for a in call['attachments']] == ['request','response']
    payloads = {a['name']:json.loads((tmp_path/a['source']).read_text()) for a in call['attachments']}
    assert payloads['request']['query'] == {'pageSize':50}
    assert payloads['response']['status_code'] == 200
    assert payloads['response']['body']['data']['userId'] == 'user-a'
    all_files = '\n'.join(p.read_text() for p in tmp_path.glob('*.json'))
    for secret in ['server-secret','refresh-secret','client-secret','auth-secret','13800000000']:
        assert secret not in all_files


@pytest.mark.parametrize('json_body',[True,False])
def test_http_error_response_is_captured(json_body):
    body = b'{"code":401,"message":"denied","accessToken":"hidden"}' if json_body else b'password=hidden denied'
    error = HTTPError('https://test.invalid',401,'Unauthorized',{'Set-Cookie':'cookie-secret'},io.BytesIO(body))
    client = HttpClient('https://test.invalid',opener=Opener(error))
    with pytest.raises(ApiError):
        client.request('POST','/api/send',body={'content':'hello'})
    response = client.journal[0]['response']
    assert response['status_code'] == 401
    assert response['body_format'] == ('json' if json_body else 'text')
    assert 'denied' in json.dumps(response)
    assert 'hidden' not in json.dumps(response)
    assert 'cookie-secret' not in json.dumps(response)


def test_network_failure_still_has_request_and_response_status():
    client = HttpClient('https://test.invalid',opener=Opener(URLError('private detail')))
    with pytest.raises(ApiError):
        client.request('GET','/api/list',params={'pageSize':50})
    assert client.journal[0]['request']['method'] == 'GET'
    assert client.journal[0]['response']['unavailable_reason'] == 'No HTTP response received'


def test_non_json_success_response_is_kept():
    client = HttpClient('https://test.invalid',opener=Opener(b'<html>gateway failure</html>'))
    with pytest.raises(ApiError):
        client.request('GET','/api/list')
    assert client.journal[0]['response']['body'] == '<html>gateway failure</html>'


def test_secret_query_is_redacted_in_encoded_url():
    client = HttpClient('https://test.invalid',opener=Opener(b'{"code":0,"data":{}}'))
    client.request('GET','/api/list',params={'access_token':'secret +/value'})
    request = client.journal[0]['request']
    assert 'secret' not in request['url']
    assert request['query']['access_token'] == '[REDACTED]'


def test_send_pacing_shared_by_text_and_cards(monkeypatch):
    from velowind_api.messages import Messages
    from velowind_api.sharing import Sharing
    from velowind_api.auth import Identity
    from velowind_api import messages
    clock = [100.0]
    sleeps = []
    monkeypatch.setattr(messages.time, 'monotonic', lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(messages.time, 'sleep', sleep)
    class Http:
        def request(self, method, path, **kwargs):
            payload = kwargs['body']
            return {'messageId':'m', 'conversationId':'ab', 'senderUserId':'a', 'receiverUserId':'b',
                    'contentType':'TEXT', 'content':payload['content'], 'clientMessageId':payload['clientMessageId'],
                    'contextCard':payload.get('context')}
    sender = Messages(Http(), Identity('a','secret'), 21)
    sender.send_text('b','text')
    assert sleeps == []
    clock[0] += 5
    Sharing(sender).post('b','post-id','share')
    assert sleeps == [16]
    clock[0] += 30
    sender.send_text('b','next')
    assert sleeps == [16]


def test_http_business_failure_visible_without_opening_attachment():
    error = HTTPError('https://test.invalid',400,'Bad request',{},io.BytesIO(
        b'{"code":17000025,"messageKey":"message.private.context_provider_unavailable","data":null}'))
    client = HttpClient('https://test.invalid',opener=Opener(error))
    with pytest.raises(ApiError,match='17000025.*message.private.context_provider_unavailable'):
        client.request('POST','/api/send',body={'content':'hello'})
    assert client.journal[0]['business_code'] == 17000025


def test_recipient_does_not_require_sender_client_id():
    from velowind_api.checks import message
    actual = {'messageId':'m','conversationId':'ab','senderUserId':'a','receiverUserId':'b',
              'contentType':'TEXT','content':'hello','direction':'INBOUND','clientMessageId':None}
    message(actual,'a','b','hello','sender-local-id','m',recipient_view=True)
    with pytest.raises(AssertionError,match='clientMessageId'):
        message(actual,'a','b','hello','sender-local-id','m')
    actual['receiverUserId'] = 'wrong'
    with pytest.raises(AssertionError,match='receiver'):
        message(actual,'a','b','hello','sender-local-id','m',recipient_view=True)
