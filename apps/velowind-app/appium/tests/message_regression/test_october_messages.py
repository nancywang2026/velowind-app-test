import pytest
from velowind_appium.message_regression.journeys import CASES, run_case
from velowind_appium.message_regression.core import Blocked


@pytest.mark.parametrize("message_case", [pytest.param((case,variant),id=case.id+"-"+variant)
                         for case in CASES for variant in case.variants])
def test_october_message_journey(message_case, regression_program):
    program, capabilities = regression_program
    case, variant = message_case
    try:
        run_case(case, variant, program, capabilities=capabilities)
    except Blocked as exc:
        pytest.fail("BLOCKED during execution (not passed): " + str(exc))
