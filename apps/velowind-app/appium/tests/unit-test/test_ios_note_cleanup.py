from types import SimpleNamespace

import pytest

from velowind_appium import cleanup
from velowind_appium.modules import message_detail


TITLE = "测试 - 长白山现场拍摄视频记录"
WRAPPED = "测试 - 长白山现场&#10;拍摄视频记录"


def card(post_id, title=WRAPPED, y=173):
    return f'<XCUIElementTypeButton name="post-home-feed-note-card-{post_id}" label="0 {title} #旅行日记 我 0" visible="true" x="13" y="{y}" width="186" height="359" />'


def listing(content):
    return f'<root name="我的笔记"><node name="my-posts-scroll-notes">{content}</node></root>'


def detail(title=WRAPPED):
    return f'<root><node name="post-detail-page"><XCUIElementTypeStaticText label="{title}" visible="true" /></node></root>'


@pytest.mark.parametrize('outcome', ['deleted', 'wrong-detail', 'card-remains'])
def test_cleanup_checks_wrapped_detail_title_and_selected_post_disappearance(monkeypatch, outcome):
    current = [listing(card('new') + card('old', y=540))]
    actions = []
    clock = [0.0]
    monkeypatch.setattr(cleanup.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(cleanup.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(cleanup, '_safe_page_source', lambda driver: current[0])
    monkeypatch.setattr(cleanup, 'swipe_vertical', lambda *a, **kw: None)
    def open_card(driver, rect):
        actions.append(('open', rect['y']))
        current[0] = detail('另一篇笔记' if outcome == 'wrong-detail' else WRAPPED)
        return True
    monkeypatch.setattr(message_detail, '_tap_rect_center', open_card)
    monkeypatch.setattr(message_detail, '_tap_ios_detail_back_button_from_source', lambda d: actions.append('back'))
    monkeypatch.setattr(cleanup, '_tap_ios_top_right_more', lambda d: actions.append('more') or True)
    monkeypatch.setattr(cleanup, 'tap_first_available_text', lambda *a: actions.append('delete') or True)
    def confirm(driver):
        current[0] = listing(card('old') + (card('new') if outcome == 'card-remains' else ''))
        return True
    monkeypatch.setattr(cleanup, 'confirm_destructive_action', confirm)
    report = cleanup.cleanup_exact_visible_item(SimpleNamespace(capabilities={'platformName': 'iOS'}), item_type='note', title=TITLE, action_texts=['删除'])
    assert actions[0] == ('open', 173)
    assert report.deleted == ([TITLE] if outcome == 'deleted' else [])
    if outcome == 'wrong-detail':
        assert 'delete' not in actions and 'more' not in actions


def test_hidden_and_similar_cards_do_not_match(monkeypatch):
    source = listing('<node visible="false">' + card('hidden') + '</node>' + card('other', TITLE + '补充'))
    monkeypatch.setattr(cleanup, '_safe_page_source', lambda d: source)
    monkeypatch.setattr(message_detail, '_tap_rect_center', lambda *a: pytest.fail('Must not open unrelated cards'))
    assert cleanup._cleanup_exact_ios_note(object(), TITLE, ['删除']).deleted == []


def test_record_ios_title_truncated_by_native_input():
    driver = SimpleNamespace()
    requested = '测试 - 长白山真的有种让人瞬间安静下来的魔力'
    actual = '测试 - 长白山真的有种让人瞬间安静下来'
    element = SimpleNamespace(get_attribute=lambda key: actual)
    message_detail._remember_ios_note_submitted_title(driver, requested, element)
    assert driver._ios_note_submitted_title == (requested, actual)


def test_cleanup_reveals_video_title_before_deleting(monkeypatch):
    current = [listing(card('video'))]
    actions = []
    monkeypatch.setattr(cleanup, '_safe_page_source', lambda d: current[0])
    def open_card(d, rect):
        current[0] = detail().replace('visible="true"', 'visible="false"')
        return True
    def reveal(d, **kw):
        actions.append('scroll')
        current[0] = detail()
    monkeypatch.setattr(message_detail, '_tap_rect_center', open_card)
    monkeypatch.setattr(cleanup, 'swipe_vertical', reveal)
    monkeypatch.setattr(cleanup, '_tap_ios_top_right_more', lambda d: actions.append('more') or True)
    monkeypatch.setattr(cleanup, 'tap_first_available_text', lambda *a: True)
    monkeypatch.setattr(cleanup, 'confirm_destructive_action', lambda d: current.__setitem__(0, listing('')))
    assert cleanup._cleanup_exact_ios_note(object(), TITLE, ['删除']).deleted == [TITLE]
    assert actions == ['scroll', 'more']


def test_published_title_matching_ignores_line_wrap():
    assert message_detail._published_note_title_matches('测试 - 长白山现场\n拍摄视频记录', TITLE)


def test_missing_ios_title_does_not_fall_back_to_merged_container():
    driver = SimpleNamespace(capabilities={'platformName': 'iOS'})
    assert not message_detail._tap_published_note_title(driver, TITLE, page_source='<root />')


def test_read_committed_title_from_form_source(monkeypatch):
    requested = '测试 - 长白山真的有种让人瞬间安静下来的魔力'
    actual = requested[:20]
    monkeypatch.setattr(message_detail, '_safe_page_source', lambda d: f'<root><XCUIElementTypeTextField name="note-title-input" value="{actual}" /></root>')
    driver = SimpleNamespace()
    message_detail._remember_ios_note_submitted_title(driver, requested)
    assert driver._ios_note_submitted_title == (requested, actual)


def test_wrong_video_detail_is_not_accepted_for_image_note():
    assert not message_detail._ios_published_detail_matches_title(detail('Velowind｜解锁-0d8bb7db'), TITLE)
    assert message_detail._ios_published_detail_matches_title(detail(), TITLE)


def test_published_title_locator_ignores_hidden_ancestor():
    source = '<root><node visible="false">' + card('hidden') + '</node></root>'
    assert message_detail._visible_ios_published_note_title_rect(source, TITLE) is None


def test_open_published_detail_returns_from_wrong_note_then_verifies_title(monkeypatch):
    driver = SimpleNamespace(capabilities={'platformName': 'iOS'})
    state = [detail('Velowind｜解锁-0d8bb7db')]
    actions = []
    monkeypatch.setattr(message_detail, '_safe_page_source', lambda d: state[0])
    monkeypatch.setattr(message_detail, 'message_detail_is_visible', lambda d: 'post-detail-page' in state[0])
    def back(d):
        actions.append('back')
        state[0] = listing(card('correct'))
        return True
    def tap(d, title, **kwargs):
        actions.append('open-correct')
        state[0] = detail()
        return True
    monkeypatch.setattr(message_detail, '_tap_ios_detail_back_button_from_source', back)
    monkeypatch.setattr(message_detail, '_tap_published_note_title', tap)
    monkeypatch.setattr(message_detail, '_my_notes_list_visible', lambda s: 'my-posts-scroll-notes' in s)
    monkeypatch.setattr(message_detail, '_wait_until', lambda predicate, timeout: predicate())
    message_detail._open_published_note_detail_from_my_notes(driver, TITLE, timeout=2)
    assert actions == ['back', 'open-correct']
    assert ''.join(driver._ios_note_submitted_title[1].split()) == ''.join(TITLE.split())
