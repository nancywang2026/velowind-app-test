"""Android regressions for unlabelled camera controls and truncated note cards."""
import pytest

from velowind_appium import cleanup
from velowind_appium.modules import photo_picker


CAMERA = '''<hierarchy><android.view.ViewGroup>
<android.view.ViewGroup><android.widget.TextView text="取消" /></android.view.ViewGroup>
<android.view.ViewGroup bounds="[544,2166][736,2358]" displayed="true">
<android.view.ViewGroup bounds="[607,2229][672,2294]" /></android.view.ViewGroup>
<android.view.ViewGroup><android.widget.TextView text="翻转" /></android.view.ViewGroup>
</android.view.ViewGroup></hierarchy>'''


def test_android_camera_uses_toolbar_bounds():
    assert photo_picker._android_camera_record_rect(CAMERA) == {
        "x": 544, "y": 2166, "width": 192, "height": 192,
    }
    assert photo_picker._android_camera_record_rect(CAMERA.replace('翻转', '其他')) is None
    assert photo_picker._android_camera_record_rect('<invalid') is None


@pytest.mark.parametrize('timer_ok', [True, False])
def test_android_camera_stops_after_five_seconds_without_queries_during_recording(monkeypatch, timer_ok):
    class Driver:
        capabilities = {"platformName": "Android"}
        recording = False
        taps = 0

        @property
        def page_source(self):
            assert not self.recording, "Do not query the moving camera timer"
            return CAMERA if self.taps == 0 else '预览视频 0:05 | 720 x 1280'

    driver = Driver()
    def tap(driver, rect, **kwargs):
        assert rect['y'] == 2166
        driver.taps += 1
        driver.recording = driver.taps == 1
        return True

    def timer(driver, seconds):
        assert seconds == 5
        assert driver.recording
        return timer_ok

    monkeypatch.setattr(photo_picker, '_adb_tap_rect_ratio', tap)
    monkeypatch.setattr(photo_picker, '_wait_for_camera_recording_duration', timer)
    monkeypatch.setattr(photo_picker, '_confirm_camera_video_selection', lambda driver: True)
    assert photo_picker._record_video_from_camera(driver) is timer_ok
    assert driver.taps == 2
    assert not driver.recording
    if timer_ok:
        assert driver._camera_video_actual_seconds == 5


@pytest.mark.parametrize('matching_detail', [True, False])
def test_android_cleanup_waits_for_cards_and_checks_full_title(monkeypatch, matching_detail):
    title = '测试 - 长白山真的有种让人瞬间安静下来的魔力'
    prefix = title[:-3]
    class Element:
        def is_displayed(self):
            return True

    class Driver:
        capabilities = {'platformName': 'Android'}
        reads = 0
        state = 'list'

        @property
        def page_source(self):
            self.reads += 1
            return '<hierarchy />' if self.reads == 1 else f'<Text text="{prefix}" />'

        def find_elements(self, by, value):
            if 'post-home-feed-note-card-' in value:
                assert prefix in value
                return [Element()]
            if 'post-detail-page' in value:
                if self.state == 'deleted':
                    return []
                return [Element()] if matching_detail else []
            raise AssertionError(value)

    driver = Driver()
    clock = [0]
    monkeypatch.setattr(cleanup.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(cleanup.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(cleanup, '_tap_element_center', lambda driver, element: setattr(driver, 'state', 'detail'))
    actions = []
    monkeypatch.setattr(cleanup, '_tap_android_note_more', lambda driver: actions.append('more') or True)
    def tap_text(driver, texts):
        actions.append(texts)
        if texts == cleanup.CONFIRM_TEXTS:
            driver.state = 'deleted'
        return True
    monkeypatch.setattr(cleanup, 'tap_first_available_text', tap_text)
    monkeypatch.setattr(cleanup, 'safe_back', lambda driver: setattr(driver, 'state', 'list'))
    report = cleanup.cleanup_exact_visible_item(driver, item_type='note', title=title, action_texts=['删除'])
    assert driver.reads >= 2
    assert report.deleted == ([title] if matching_detail else [])
    if not matching_detail:
        assert actions == []
        assert report.skipped == [title]


def test_ios_recording_does_not_enter_android_path(monkeypatch):
    driver = type('Driver', (), {'capabilities': {'platformName': 'iOS'}})()
    monkeypatch.setattr(photo_picker, '_record_android_video_from_camera', lambda *a, **kw: pytest.fail('Android branch on iOS'))
    monkeypatch.setattr(photo_picker, '_wait_until', lambda predicate, timeout: False)
    assert photo_picker._record_video_from_camera(driver, record_seconds=5) is False


def test_ios_cleanup_does_not_enter_android_path(monkeypatch):
    driver = type('Driver', (), {'capabilities': {'platformName': 'iOS'}})()
    monkeypatch.setattr(cleanup, '_cleanup_exact_android_note', lambda *a, **kw: pytest.fail('Android branch on iOS'))
    monkeypatch.setattr(cleanup, '_tap_exact_visible_title', lambda driver, title: False)
    assert cleanup.cleanup_exact_visible_item(driver, item_type='note', title='测试', action_texts=['删除']).deleted == []


def test_android_cleanup_uses_title_accepted_by_native_input(monkeypatch):
    from velowind_appium.modules import message_detail
    from tests import shared_publish_note
    title = '测试 - 长白山真的有种让人瞬间安静下来的魔力'
    actual = title[:20]
    driver = type('Driver', (), {'capabilities': {'platformName': 'Android'},
        'page_source': f'<hierarchy><android.widget.EditText hint="添加标题" text="{actual}" /></hierarchy>'})()
    message_detail._remember_android_note_submitted_title(driver, title)
    calls = []
    def delete(driver, title, config):
        calls.append(title)
        return cleanup.CleanupReport('note', [title], [])
    monkeypatch.setattr(shared_publish_note, 'cleanup_published_note', delete)
    report = shared_publish_note.cleanup_published_note_after_success(driver, object(), title)
    assert calls == [actual]
    assert report.deleted == [actual]
    # A different case must not inherit this note's shortened title.
    shared_publish_note.cleanup_published_note_after_success(driver, object(), '另一个标题')
    assert calls[-1] == '另一个标题'
    driver.capabilities = {'platformName': 'iOS'}
    shared_publish_note.cleanup_published_note_after_success(driver, object(), title)
    assert calls[-1] == title
