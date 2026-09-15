import io
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from velowind_appium import cleanup
from velowind_appium import note_api_cleanup as api

POST_ID = 'pst-34c1215433d94a13823dbbd6937507fc'
TITLE = '测试笔记'


def card(post_id=POST_ID):
    return f'<XCUIElementTypeButton name="post-home-feed-note-card-{post_id}" label="0 {TITLE} #旅行 我 0" visible="true" />'


def test_extract_ios_and_android():
    assert api.note_post_ids_from_xml(card(), TITLE) == [POST_ID]
    source = f'<node resource-id="com.app:id/post-home-feed-note-card-{POST_ID}"><android.widget.TextView text="{TITLE}" /></node>'
    assert api.note_post_ids_from_xml(source, TITLE) == [POST_ID]


@pytest.mark.parametrize('source', [
    '<bad', '<root visible="false">' + card() + '</root>',
    card().replace(TITLE, TITLE + '其他'), card().replace(TITLE, '测试…'),
    card().replace(POST_ID, 'pst-invalid'),
])
def test_unmatched_or_hidden_xml(source):
    assert api.note_post_ids_from_xml(source, TITLE) == []


def test_http_contract(monkeypatch):
    requests = []
    results = [{'code': 0, 'data': {'accessToken': 'test-token'}},
               {'code': 0, 'data': {'postId': POST_ID, 'deleted': True}}]
    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 20
            return io.StringIO(json.dumps(results.pop(0)))
    monkeypatch.setattr(api, 'build_opener', lambda *args: Opener())
    api.delete_note_via_api(POST_ID, 'test-phone', 'test-password')
    login, delete = requests
    assert login.method == 'POST'
    assert login.full_url.endswith('/auth/login/phone/password')
    assert json.loads(login.data) == {'phone': 'test-phone', 'password': 'test-password'}
    assert delete.method == 'DELETE'
    assert delete.full_url.endswith('/posts/' + POST_ID)
    assert delete.get_header('Authorization') == 'Bearer test-token'
    assert UUID(login.get_header('X-request-id')) != UUID(delete.get_header('X-request-id'))


@pytest.mark.parametrize('result', [{'code': 401, 'data': {}}, {'code': 0, 'data': None}, 'bad'])
def test_business_error(monkeypatch, result):
    monkeypatch.setattr(api, 'build_opener', lambda *args: SimpleNamespace(
        open=lambda *args, **kwargs: io.StringIO(json.dumps(result))))
    with pytest.raises(api.NoteCleanupApiError):
        api.delete_note_via_api(POST_ID, 'phone', 'password')


def test_missing_token_does_not_delete(monkeypatch):
    calls = []
    monkeypatch.setattr(api, '_request_data', lambda *a, **kw: calls.append(a) or {})
    with pytest.raises(api.NoteCleanupApiError):
        api.delete_note_via_api(POST_ID, 'phone', 'password')
    assert len(calls) == 1


def test_missing_saved_id_never_looks_up_xml_or_deletes(monkeypatch):
    monkeypatch.setattr(api, 'delete_note_via_api', lambda *a: pytest.fail('must not delete'))
    with pytest.raises(api.NoteCleanupApiError):
        cleanup.cleanup_published_note_via_api(object(), TITLE, object())


@pytest.mark.parametrize('mode', ['ui', 'api'])
def test_mode_routes_and_leaves_page(monkeypatch, mode):
    monkeypatch.setenv('VW_NOTE_CLEANUP_MODE', mode)
    calls = []
    monkeypatch.setattr(cleanup, 'ensure_logged_in_on_home', lambda *a: None)
    monkeypatch.setattr(cleanup, '_open_me_entry', lambda *a: None)
    monkeypatch.setattr(cleanup, 'safe_back', lambda *a: calls.append('back'))
    monkeypatch.setattr(cleanup, 'cleanup_exact_visible_item', lambda *a, **kw: calls.append('ui'))
    monkeypatch.setattr(cleanup, 'cleanup_published_note_via_api', lambda *a: calls.append('api'))
    cleanup.cleanup_published_note(object(), TITLE, object())
    assert calls == (['ui', 'back'] if mode == 'ui' else ['api'])


def test_invalid_mode(monkeypatch):
    monkeypatch.setenv('VW_NOTE_CLEANUP_MODE', 'oops')
    with pytest.raises(ValueError):
        cleanup.cleanup_published_note(object(), TITLE, object())


@pytest.mark.parametrize('deleted', [False, True])
def test_checks_deleted_post_identity(monkeypatch, deleted):
    responses = iter([{'accessToken': 'token'}, {'postId': 'pst-' + 'b' * 32, 'deleted': deleted}])
    monkeypatch.setattr(api, '_request_data', lambda *a, **kw: next(responses))
    with pytest.raises(api.NoteCleanupApiError):
        api.delete_note_via_api(POST_ID, 'phone', 'password')


def test_api_cleanup_uses_selected_id_and_configured_account(monkeypatch):
    calls = []
    monkeypatch.setattr(api, 'delete_note_via_api', lambda *a: calls.append(a))
    config = SimpleNamespace(login_username='phone', login_password='password')
    report = cleanup.cleanup_published_note_via_api(SimpleNamespace(_api_note_publication={"requested_title": TITLE, "published_title": TITLE, "post_id": POST_ID}), TITLE, config)
    assert calls == [(POST_ID, 'phone', 'password')]
    assert report.deleted == [TITLE]


def test_allure_records_request_response_and_redacts_secrets(monkeypatch):
    attachments = []
    monkeypatch.setattr(api, 'attach_text', lambda name, body: attachments.append(json.loads(body)))
    class Response(io.StringIO):
        status = 200
        headers = {'Content-Type': 'application/json', 'Set-Cookie': 'session=private'}
    monkeypatch.setattr(api, 'build_opener', lambda *a: SimpleNamespace(open=lambda *a, **kw: Response(
        json.dumps({'code': 0, 'data': {'accessToken': 'secret-token', 'refreshToken': 'refresh-secret'}}))))
    api._request_data('POST', 'https://example.test/login', body={'phone': 'phone', 'password': 'secret-password'})
    record = attachments[0]
    assert record['request']['method'] == 'POST'
    assert record['response']['status'] == 200
    assert record['duration_ms'] >= 0
    assert record['outcome'] == 'success'
    rendered = json.dumps(record)
    for secret in ('secret-token', 'refresh-secret', 'secret-password', 'session=private'):
        assert secret not in rendered


def test_http_failure_is_attached(monkeypatch):
    from urllib.error import HTTPError
    attachments = []
    monkeypatch.setattr(api, 'attach_text', lambda name, body: attachments.append(json.loads(body)))
    def fail(*a, **kw):
        raise HTTPError('https://example.test', 403, 'Forbidden', {},
                        io.BytesIO(b'{"code":403,"message":"not author"}'))
    monkeypatch.setattr(api, 'build_opener', lambda *a: SimpleNamespace(open=fail))
    with pytest.raises(api.NoteCleanupApiError):
        api._request_data('DELETE', 'https://example.test', token='private-token')
    assert attachments[0]['response']['status'] == 403
    assert attachments[0]['response']['body']['code'] == 403
    assert attachments[0]['outcome'] == 'failed'
    assert 'private-token' not in json.dumps(attachments)


def test_capture_only_current_publication_and_ignore_old_titles():
    driver = SimpleNamespace(_api_note_publication={"requested_title": "original", "published_title": TITLE, "post_id": None})
    api.remember_published_post_id(driver, card(), 'old title')
    assert driver._api_note_publication['post_id'] is None
    api.remember_published_post_id(driver, card(), TITLE)
    assert driver._api_note_publication['post_id'] == POST_ID


def test_saved_id_cleanup_is_idempotent_and_does_not_read_xml(monkeypatch):
    calls = []
    monkeypatch.setattr(api, 'delete_note_via_api', lambda *args: calls.append(args))
    driver = SimpleNamespace(_api_note_publication={"requested_title": TITLE, "published_title": TITLE, "post_id": POST_ID})
    config = SimpleNamespace(login_username='phone', login_password='password')
    cleanup.cleanup_published_note_via_api(driver, TITLE, config)
    cleanup.cleanup_published_note_via_api(driver, TITLE, config)
    assert len(calls) == 1
    with pytest.raises(api.NoteCleanupApiError):
        cleanup.cleanup_published_note_via_api(driver, 'another case', config)


def test_publish_resets_old_id_and_captures_new_id_before_cleanup(monkeypatch):
    from velowind_appium.modules import message_detail as detail
    monkeypatch.setenv('VW_NOTE_CLEANUP_MODE', 'api')
    driver = SimpleNamespace(_api_note_publication={'post_id': 'old'}, capabilities={})
    monkeypatch.setattr(detail, 'open_message_note_publisher', lambda *a, **kw: None)
    monkeypatch.setattr(detail, 'fill_message_note_form', lambda *a, **kw: None)
    monkeypatch.setattr(detail, 'submit_message_note', lambda *a, **kw: '成功')
    def validate(driver, title, **kwargs):
        assert driver._api_note_publication['post_id'] is None
        assert title != TITLE
        api.remember_published_post_id(driver, card().replace(TITLE, title), title)
    monkeypatch.setattr(detail, '_validate_published_note_image_matches_uploaded_preview', validate)
    draft = detail.MessageNoteDraft(title=TITLE, body='正文', topics=[], location='', media_type='image')
    assert detail.publish_message_note(driver, draft) == '成功'
    assert driver._api_note_publication['post_id'] == POST_ID
    assert driver._api_note_publication['requested_title'] == TITLE


def test_persistent_mode_and_environment_override(monkeypatch):
    from velowind_appium import cleanup_config
    monkeypatch.delenv('VW_NOTE_CLEANUP_MODE', raising=False)
    monkeypatch.setattr(cleanup_config, '_read_yaml_config', lambda: {'cleanup': {'note_cleanup_mode': 'api'}})
    assert cleanup_config.note_cleanup_mode() == 'api'
    assert api.api_cleanup_enabled()
    monkeypatch.setenv('VW_NOTE_CLEANUP_MODE', 'ui')
    assert cleanup_config.note_cleanup_mode() == 'ui'
    assert not api.api_cleanup_enabled()
