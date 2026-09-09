import pytest

pytestmark = [pytest.mark.message_system, pytest.mark.skip_home_session]


def test_message_business_flow(message_flow, step):
    step(f'{message_flow.case_id}-{message_flow.variant}', message_flow.run)
