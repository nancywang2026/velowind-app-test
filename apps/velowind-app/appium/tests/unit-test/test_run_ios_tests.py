from pathlib import Path
import sys

import pytest

from velowind_appium import run_ios_tests


def test_load_test_suite_supports_cases_and_markers(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - smoke/test_ios_feature_walkthrough.py
  - message/test_ios_publish_note.py
markers:
  - smoke
  - full
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    suite = run_ios_tests.load_test_suite(suite_file)

    assert suite.tests == [
        "smoke/test_ios_feature_walkthrough.py",
        "message/test_ios_publish_note.py",
    ]
    assert suite.markers == ["smoke", "full"]
    assert suite.pytest_args == ["--maxfail=1"]


def test_build_pytest_command_uses_suite_file(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - smoke/test_ios_feature_walkthrough.py
markers:
  - smoke
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    command = run_ios_tests.build_pytest_command(["--suite", str(suite_file)])

    assert command[:4] == [sys.executable, "-m", "pytest", str(run_ios_tests.TEST_PATH)]
    assert "-q" in command
    assert str(run_ios_tests.TEST_PATH / "smoke" / "test_ios_feature_walkthrough.py") in command
    assert "--maxfail=1" in command
    marker_index = max(index for index, value in enumerate(command) if value == "-m")
    assert command[marker_index + 1] == "smoke"


def test_build_pytest_command_rejects_empty_suite_file(tmp_path):
    suite_file = tmp_path / "empty.yaml"
    suite_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        run_ios_tests.build_pytest_command(["--suite", str(suite_file)])
