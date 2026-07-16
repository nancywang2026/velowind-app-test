import pytest

from tests.shared_publish_note import publish_note_use_case_ids, run_publish_note_case


@pytest.mark.full
@pytest.mark.parametrize("use_case_id", publish_note_use_case_ids())
def test_user_can_publish_note_for_review(driver, ios_config, step, use_case_id):
    run_publish_note_case(
        driver,
        ios_config,
        step,
        use_case_id,
        verification_label="message-note-publish-verification-points",
        assertion_label="iOS",
    )
