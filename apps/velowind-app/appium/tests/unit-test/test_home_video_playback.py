from io import BytesIO
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from velowind_appium.modules import home_video_playback as playback
from velowind_appium.modules.home_camera_badge import camera_outline_position


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
    step_statuses = []
    @contextmanager
    def record_step(name):
        try:
            yield
        except AssertionError:
            step_statuses.append('failed')
            raise
        else:
            step_statuses.append('passed')
    monkeypatch.setattr(playback.allure, 'step', record_step)
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
    assert step_statuses == ['failed' if result else 'passed' for result in outcomes[:expected_calls]]


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


@pytest.mark.parametrize('source,expected', [
    ('<root label="寻风集 视频暂时不可播放"><node name="视频暂时不可播放" visible="false" /></root>', ''),
    ('<root label="视频暂时不可播放"><node name="视频暂时不可播放" visible="false" /></root>', ''),
    ('<root><node visible="false"><node name="post-detail-video-error" visible="true" /></node></root>', ''),
    ('<root><node name="视频暂时不可播放" visible="true" /></root>', '视频暂时不可播放'),
    ('<root><node resource-id="com.app:id/post-detail-video-error"><node name="视频暂时不可播放" visible="false" /></node></root>', 'post-detail-video-error'),
])
def test_error_detection_ignores_stale_ancestor_labels(source, expected):
    assert playback._playback_state_source(source) == expected


def test_error_disappearing_during_screenshot_requires_actual_playback_check(monkeypatch, tmp_path):
    clock = [0.0]
    monkeypatch.setattr(playback.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(playback.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    class Driver:
        reads = 0
        frames = 0
        @property
        def page_source(self):
            self.reads += 1
            return DETAIL.format('<node name="视频暂时不可播放" />' if self.reads == 1 else '')
        def get_window_size(self):
            return {'width': 200, 'height': 200}
        def get_screenshot_as_png(self):
            self.frames += 1
            return frame_png(self.frames, 'moving')
    driver = Driver()
    assert playback.check_video_playback(driver, tmp_path, timeout=15) is None
    assert clock[0] >= 8
    assert list(tmp_path.glob('transient-state-*-before.xml'))
    assert list(tmp_path.glob('transient-state-*-after.xml'))
    assert not (tmp_path / 'playback-error.png').exists()


def test_unmarked_photo_card_is_not_a_video_candidate():
    source = '<root><XCUIElementTypeButton name="post-home-feed-note-card-pst-123" label="测试 Nancy 1" visible="true" x="4" y="130" width="195" height="308" /></root>'
    assert playback.visible_home_videos(source, {'width': 402, 'height': 874}) == []


def test_only_camera_marked_card_is_selected_from_mixed_feed():
    source = '<root><node name="post-home-feed-note-card-photo" x="4" y="130" width="195" height="308" /><node name="post-home-feed-note-card-video" x="204" y="130" width="195" height="308">' + badge('video') + '</node></root>'
    assert [video.post_id for video in playback.visible_home_videos(source, {'width': 402, 'height': 874})] == ['video']


@pytest.mark.parametrize('name,expected', [('video', True), ('video_occluded', False), ('photo_group', False), ('photo_bus', False)])
def test_camera_recognition_from_real_device_corners(name, expected):
    with Image.open(Path(__file__).parent / 'fixtures/home_camera' / f'{name}.png') as corner:
        assert (camera_outline_position(corner) is not None) is expected


@pytest.mark.parametrize('color', ['white', 'black', '#777777'])
def test_solid_corner_is_not_camera(color):
    assert camera_outline_position(Image.new('RGB', (126, 126), color)) is None


@pytest.mark.parametrize('scale', [2, 3])
def test_screenshot_camera_selects_video_without_accessibility_badge(scale):
    screenshot = Image.new('RGB', (402 * scale, 874 * scale), '#777777')
    with Image.open(Path(__file__).parent / 'fixtures/home_camera/video.png') as corner:
        screenshot.paste(corner.resize((42 * scale, 42 * scale)), (155 * scale, 606 * scale))
    output = BytesIO()
    screenshot.save(output, format='PNG')
    # The video card extends below the screen, but its corner is visible.
    source = '<root><node name="post-home-feed-note-card-video" x="4" y="604" width="195" height="308" /><node name="post-home-feed-note-card-photo" x="203" y="347" width="195" height="328" /></root>'
    videos = playback.visible_home_videos(source, {'width': 402, 'height': 874}, output.getvalue())
    assert [video.post_id for video in videos] == ['video']
    assert 165 < videos[0].bounds.x < 185
    assert 610 < videos[0].bounds.y < 635


def test_photo_only_feed_never_opens_detail_or_counts_as_video(monkeypatch, tmp_path):
    class Driver:
        page_source = '<root><node name="post-home-feed-note-card-photo" x="4" y="130" width="195" height="308" /></root>'
        def get_window_size(self):
            return {'width': 402, 'height': 874}
        def execute_script(self, *args):
            pytest.fail('Unmarked photo must not be opened')
    monkeypatch.setattr(playback, 'wait_for_home_feed', lambda *a, **k: None)
    with pytest.raises(AssertionError, match='0/4'):
        playback.verify_four_home_videos(Driver(), tmp_path, max_swipes=0)


def test_first_four_photos_are_skipped_then_four_videos_checked(monkeypatch, tmp_path):
    photos = '<root>' + ''.join(f'<node name="post-home-feed-note-card-photo-{i}" x="4" y="130" width="195" height="308" />' for i in range(4)) + '</root>'
    videos = '<root>' + ''.join(badge(str(i)) for i in range(4)) + '</root>'
    class Driver:
        page_source = photos
        taps = 0
        def get_window_size(self):
            return {'width': 402, 'height': 874}
        def execute_script(self, *args):
            assert self.page_source == videos
            self.taps += 1
            self.page_source = DETAIL.format('')
    driver = Driver()
    checks = []
    monkeypatch.setattr(playback, 'wait_for_home_feed', lambda *a, **k: None)
    monkeypatch.setattr(playback, '_return_to_feed', lambda d: setattr(d, 'page_source', videos))
    monkeypatch.setattr(playback, 'swipe_vertical', lambda d, **k: setattr(d, 'page_source', videos))
    monkeypatch.setattr(playback.time, 'sleep', lambda *a: None)
    monkeypatch.setattr(playback, 'check_video_playback', lambda *a: checks.append(True))
    playback.verify_four_home_videos(driver, tmp_path, max_swipes=1)
    assert driver.taps == len(checks) == 4


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
