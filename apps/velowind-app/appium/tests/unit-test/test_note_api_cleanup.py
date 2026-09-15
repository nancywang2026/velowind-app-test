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


def test_ambiguous_title_never_deletes(monkeypatch):
    source = '<root>' + card() + card('pst-' + 'a' * 32) + '</root>'
    monkeypatch.setattr(api, 'delete_note_via_api', lambda *a: pytest.fail('must not delete'))
    report = cleanup.cleanup_published_note_via_api(SimpleNamespace(page_source=source), TITLE, object())
    assert report.deleted == []
    assert report.skipped == [TITLE]


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
    assert calls == [mode, 'back']


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
    report = cleanup.cleanup_published_note_via_api(SimpleNamespace(page_source=card()), TITLE, config)
    assert calls == [(POST_ID, 'phone', 'password')]
    assert report.deleted == [TITLE]
