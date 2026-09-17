import pytest

from velowind_appium.modules.home_video_playback import verify_four_home_videos
from velowind_appium.session import dismiss_common_system_alerts, ensure_read_session_on_home


@pytest.mark.full
@pytest.mark.smoke
@pytest.mark.restore_home_after
def test_four_home_videos_play_normally(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    step("verify-four-home-videos", lambda: verify_four_home_videos(driver, ios_config.artifact_dir))
