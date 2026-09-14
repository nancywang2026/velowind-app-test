from io import BytesIO

from PIL import Image, ImageDraw
import pytest

from velowind_appium.modules import home_video_playback as playback


HOME = '<root name="post-home-feed-category-pager" />'
DETAIL = '<root name="post-detail-page"><node name="post-detail-video-surface" x="0" y="0" width="200" height="200" />{}</root>'


def badge(post_id, extra=''):
    return f'<node name="post-home-feed-note-video-badge-{post_id}" x="20" y="150" width="30" height="30" {extra}/>'


def test_video_discovery_deduplicates_and_excludes_hidden_and_offscreen():
    source = '<root>' + badge('one') + badge('one') + badge('two', 'visible="false"') + '<node displayed="false">' + badge('three') + '</node>' + badge('four').replace('y="150"', 'y="500"') + '</root>'
    assert [video.post_id for video in playback.visible_home_videos(source, {'width': 400, 'height': 400})] == ['one']


def test_android_badge_resource_id_is_supported():
    source = '<hierarchy><node resource-id="com.velowind.rider:id/post-home-feed-note-video-badge-abc" bounds="[10,150][40,180]" /></hierarchy>'
    assert playback.visible_home_videos(source, {'width': 400, 'height': 400})[0].post_id == 'abc'


def test_aggregated_card_text_does_not_identify_a_video():
    assert playback.visible_home_videos('<root>' + badge('abc').replace('name="post-', 'name="some title post-') + '</root>', {'width': 400, 'height': 400}) == []


@pytest.mark.parametrize('outcomes,expected_calls,failed', [
    ([None] * 4, 4, False),
    (['broken', None, None, None], 4, True),
    ([None, 'broken', None, None], 4, True),
    ([None, None, None, 'broken'], 4, True),
    (['broken', 'broken', None, None], 2, True),
    (['broken', None, 'broken', None], 3, True),
    ([None, None, 'broken', 'broken'], 4, True),
])
def test_four_video_thresholds(monkeypatch, tmp_path, outcomes, expected_calls, failed):
    class Driver:
        page_source = HOME
        def get_window_size(self):
            return {'width': 400, 'height': 800}
        def execute_script(self, *args):
            self.page_source = DETAIL.format('')
    driver = Driver()
    calls = []
    videos = [playback.HomeVideo(str(index), playback.VideoBounds(20, 150, 30, 30)) for index in range(4)]
    monkeypatch.setattr(playback, 'wait_for_home_feed', lambda *a, **k: None)
    monkeypatch.setattr(playback, 'safe_back', lambda d: setattr(d, 'page_source', HOME))
    monkeypatch.setattr(playback, 'visible_home_videos', lambda *a: videos)
    def check(*args):
        calls.append(True)
        return outcomes[len(calls) - 1]
    monkeypatch.setattr(playback, 'check_video_playback', check)
    if failed:
        with pytest.raises(AssertionError, match='视频播放失败'):
            playback.verify_four_home_videos(driver, tmp_path)
    else:
        playback.verify_four_home_videos(driver, tmp_path)
    assert len(calls) == expected_calls


def test_repeated_video_does_not_fill_four_samples(monkeypatch, tmp_path):
    class Driver:
        page_source = HOME
        def get_window_size(self):
            return {'width': 400, 'height': 800}
        def execute_script(self, *args):
            pass
    calls = []
    monkeypatch.setattr(playback, 'wait_for_home_feed', lambda *a, **k: None)
    monkeypatch.setattr(playback, 'visible_home_videos', lambda *a: [playback.HomeVideo('same', playback.VideoBounds(20, 150, 30, 30))])
    monkeypatch.setattr(playback, 'check_video_playback', lambda *a: calls.append(True))
    monkeypatch.setattr(playback, 'swipe_vertical', lambda *a, **k: None)
    monkeypatch.setattr(playback.time, 'sleep', lambda *a: None)
    with pytest.raises(AssertionError, match='1/4'):
        playback.verify_four_home_videos(Driver(), tmp_path, max_swipes=2)
    assert len(calls) == 1


def frame_png(index, mode):
    frame = Image.new('RGB', (200, 200), 'black' if mode == 'black' else '#446688')
    if mode != 'black':
        x = 40 + (index % 3) * 25 if mode == 'moving' else 40
        ImageDraw.Draw(frame).rectangle((x, 40, x + 30, 150), fill='white')
    output = BytesIO()
    frame.save(output, format='PNG')
    return output.getvalue()


@pytest.mark.parametrize('mode,marker,passed', [
    ('moving', '', True),
    ('static', '', False),
    ('black', '', False),
    ('moving', 'post-detail-video-loading', False),
    ('moving', 'post-detail-video-cover', False),
    ('moving', 'post-detail-video-error', False),
    ('moving', 'post-detail-video-paused-overlay', False),
])
def test_playback_requires_sustained_rendered_motion(monkeypatch, tmp_path, mode, marker, passed):
    clock = [0.0]
    monkeypatch.setattr(playback.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(playback.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    class Driver:
        page_source = DETAIL.format(f'<node name="{marker}" />' if marker else '')
        index = 0
        def get_window_size(self):
            return {'width': 200, 'height': 200}
        def get_screenshot_as_png(self):
            self.index += 1
            return frame_png(self.index, mode)
    reason = playback.check_video_playback(Driver(), tmp_path, timeout=12, observe_seconds=8)
    assert (reason is None) is passed


def test_playback_that_freezes_after_initial_motion_fails(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(playback.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(playback.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    class Driver:
        page_source = DETAIL.format('')
        index = 0
        def get_window_size(self):
            return {'width': 200, 'height': 200}
        def get_screenshot_as_png(self):
            self.index += 1
            return frame_png(min(self.index, 3), 'moving')
    assert '画面未持续变化' in playback.check_video_playback(Driver(), tmp_path, timeout=12)


def test_loading_overlay_appearing_during_capture_cannot_pass(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(playback.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(playback.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    class Driver:
        index = 0
        reads = 0
        @property
        def page_source(self):
            self.reads += 1
            return DETAIL.format('<node name="post-detail-video-loading" />' if self.reads % 2 == 0 else '')
        def get_window_size(self):
            return {'width': 200, 'height': 200}
        def get_screenshot_as_png(self):
            self.index += 1
            return frame_png(self.index, 'moving')
    assert playback.check_video_playback(Driver(), tmp_path, timeout=12) is not None


def test_ios_merged_badge_falls_back_to_card_id():
    source = '<root><XCUIElementTypeButton name="post-home-feed-note-card-pst-123" label="测试 Nancy 1" visible="true" x="4" y="130" width="195" height="308" /></root>'
    cards = playback.visible_home_videos(source, {'width': 402, 'height': 874})
    assert len(cards) == 1
    assert cards[0].post_id == 'pst-123'
    assert cards[0].confirmed_video is False


@pytest.mark.parametrize('source,expected', [
    (DETAIL.format('<node name="post-detail-banner-pager" label="写留言" />'), True),
    ('<root><node name="post-detail-banner-pager" label="写留言" /></root>', False),
])
def test_detail_classification_precedes_counting(source, expected):
    class Driver:
        page_source = source
    assert playback._detail_is_video(Driver()) is expected


def test_error_description_includes_visible_message_without_inventing_root_cause():
    description = playback._playback_error_reason('post-detail-video-error 视频暂时不可用 视频错误，请稍后再试。', 'post-detail-video-error')
    assert '进入视频详情后播放失败' in description
    assert '视频暂时不可用' in description
    assert '视频错误，请稍后再试。' in description
    assert '网络' not in description


def test_ios_returns_using_visible_back_control(monkeypatch):
    class Driver:
        capabilities = {'platformName': 'iOS'}
    actions = []
    monkeypatch.setattr(playback, '_tap_ios_detail_back_button_from_source', lambda driver: actions.append('tap') or True)
    monkeypatch.setattr(playback, 'safe_back', lambda driver: actions.append('driver.back'))
    monkeypatch.setattr(playback, 'wait_for_home_feed', lambda *a, **k: actions.append('home-ready'))
    playback._return_to_feed(Driver())
    assert actions == ['tap', 'home-ready']
