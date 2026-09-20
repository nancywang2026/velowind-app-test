import os

import pytest

from velowind_appium.modules.home_video_playback import verify_four_home_videos
from velowind_appium.session import dismiss_common_system_alerts, ensure_read_session_on_home


# Override the default sample size with VW_HOME_VIDEO_COUNT.
HOME_VIDEO_COUNT = int(os.environ.get("VW_HOME_VIDEO_COUNT", "2"))


@pytest.mark.full
@pytest.mark.smoke
@pytest.mark.restore_home_after
def test_four_home_videos_play_normally(driver, ios_config, step):
    dismiss_common_system_alerts(driver, step)
    step("prepare-home-session", lambda: ensure_read_session_on_home(driver, ios_config))
    step(f"verify-{HOME_VIDEO_COUNT}-home-videos", lambda: verify_four_home_videos(
        driver, ios_config.artifact_dir, video_count=HOME_VIDEO_COUNT,
    ))
