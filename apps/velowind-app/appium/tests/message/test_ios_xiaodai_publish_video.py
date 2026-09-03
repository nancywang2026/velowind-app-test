import pytest

from tests.message.xiaodai_video_upload import run_xiaodai_video_upload_case, xiaodai_video_use_case_ids


@pytest.mark.full
@pytest.mark.skip_home_session
@pytest.mark.parametrize("use_case_id", xiaodai_video_use_case_ids())
def test_user_can_publish_xiaodai_video_note_for_review(driver, ios_config, step, use_case_id):
    run_xiaodai_video_upload_case(driver, ios_config, step, use_case_id)
