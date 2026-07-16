from pathlib import Path
import sys

import pytest

from velowind_appium import run_android_tests


def test_load_android_test_suite_supports_cases_and_markers(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - android_smoke/test_android_feature_walkthrough.py
markers:
  - smoke
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    suite = run_android_tests.load_test_suite(suite_file)

    assert suite.tests == ["android_smoke/test_android_feature_walkthrough.py"]
    assert suite.markers == ["smoke"]
    assert suite.pytest_args == ["--maxfail=1"]


def test_build_android_pytest_command_uses_suite_file(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - android_smoke/test_android_feature_walkthrough.py
markers:
  - smoke
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    command = run_android_tests.build_pytest_command(["--suite", str(suite_file)])

    assert command[:4] == [sys.executable, "-m", "pytest", str(run_android_tests.TEST_PATH)]
    assert "-q" in command
    assert str(run_android_tests.TEST_PATH / "android_smoke" / "test_android_feature_walkthrough.py") in command
    assert "--maxfail=1" in command
    marker_index = max(index for index, value in enumerate(command) if value == "-m")
    assert command[marker_index + 1] == "smoke"


def test_build_android_pytest_command_rejects_empty_suite_file(tmp_path):
    suite_file = tmp_path / "empty.yaml"
    suite_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        run_android_tests.build_pytest_command(["--suite", str(suite_file)])


def test_android_runner_uses_android_artifact_paths():
    assert run_android_tests.ALLURE_RESULTS == Path(run_android_tests.REPO_ROOT) / ".tmp" / "appium-android" / "allure-results"
    assert run_android_tests.ALLURE_REPORT == Path(run_android_tests.REPO_ROOT) / ".tmp" / "appium-android" / "allure-report"


def test_android_runner_selects_android_platform(monkeypatch):
    monkeypatch.delenv("VW_APPIUM_PLATFORM", raising=False)
    monkeypatch.setattr(run_android_tests.sys, "argv", ["run_android_tests", "--all"])
    monkeypatch.setattr(
        run_android_tests,
        "_run",
        lambda command: type("Result", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(run_android_tests, "_generate_and_open_report", lambda: None)

    assert run_android_tests.main() == 0
    assert run_android_tests.os.environ["VW_APPIUM_PLATFORM"] == "android"
