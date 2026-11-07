import json
import pytest
from velowind_api.reporting import write_allure
from velowind_api.scenario import new_report


@pytest.mark.parametrize("state,error_type,expected", [("passed",None,"passed"), ("failed","AssertionError","failed"), ("failed","ApiError","broken"), ("blocked","ConfigError","broken")])
def test_allure_status_steps_and_attachment(tmp_path, state, error_type, expected):
    report = new_report()
    report.update(status=state, error_type=error_type)
    if error_type:
        report["error"] = "safe failure"
    report["steps"] = [{"name":"01 测试步骤", "status":"failed" if error_type else "passed",
                        "error_type":error_type, "start":1000,"stop":2000}]
    write_allure(report, tmp_path)
    result = json.loads(next(tmp_path.glob('*-result.json')).read_text())
    assert result['status'] == expected
    assert result['steps'][0]['start'] == 1000
    assert result['steps'][0]['stop'] == 2000
    assert (tmp_path / result['attachments'][0]['source']).is_file()
    write_allure(report, tmp_path)
    assert len(list(tmp_path.glob('*-result.json'))) == 2


def test_config_check_has_distinct_test_identity(tmp_path):
    report = new_report()
    report['status'] = 'config_validated'
    write_allure(report, tmp_path, config_only=True)
    result = json.loads(next(tmp_path.glob('*-result.json')).read_text())
    assert result['fullName'] == 'velowind_api.config_check'
    assert result['status'] == 'passed'
