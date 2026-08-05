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


def test_load_test_suite_supports_file_methods(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - file: smoke/test_ios_feature_walkthrough.py
    methods:
      - test_ios_home_categories_are_reachable
      - test_ios_bottom_tabs_are_reachable
  - message/test_ios_publish_note.py
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    suite = run_ios_tests.load_test_suite(suite_file)

    assert suite.tests == [
        "smoke/test_ios_feature_walkthrough.py::test_ios_home_categories_are_reachable",
        "smoke/test_ios_feature_walkthrough.py::test_ios_bottom_tabs_are_reachable",
        "message/test_ios_publish_note.py",
    ]
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


def test_build_pytest_command_uses_isolated_allure_run_dir(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_RUN_ID", "ios-run-1")

    command = run_ios_tests.build_pytest_command(["-m", "smoke"])

    assert f"--alluredir={run_ios_tests.REPO_ROOT / '.tmp' / 'appium-ios' / 'runs' / 'ios-run-1' / 'allure-results'}" in command
    assert f"--alluredir={run_ios_tests.REPO_ROOT / '.tmp' / 'appium-ios' / 'allure-results'}" not in command


def test_build_pytest_command_allows_allure_result_dir_override(monkeypatch, tmp_path):
    results_dir = tmp_path / "custom-results"
    monkeypatch.setenv("VW_ALLURE_RESULTS_DIR", str(results_dir))

    command = run_ios_tests.build_pytest_command(["-m", "smoke"])

    assert f"--alluredir={results_dir}" in command


def test_build_pytest_command_rejects_empty_suite_file(tmp_path):
    suite_file = tmp_path / "empty.yaml"
    suite_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        run_ios_tests.build_pytest_command(["--suite", str(suite_file)])


def test_ios_full_suite_contains_required_regression_cases():
    suite_file = (
        Path(run_ios_tests.REPO_ROOT)
        / "apps"
        / "velowind-app"
        / "appium"
        / "test-suites"
        / "ios-full.yaml"
    )

    suite = run_ios_tests.load_test_suite(suite_file)

    assert suite.tests == [
        "smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough",
        "smoke/test_ios_feature_walkthrough.py::test_bottom_tabs_are_reachable",
        "message/test_ios_search_by_type.py::test_user_can_filter_notes_by_type",
        "message/test_ios_search_note.py::test_user_can_search_and_open_note",
        "message/test_ios_publish_note.py::test_user_can_publish_note_for_review",
        "draft/test_ios_save_note_draft.py::test_user_can_save_note_as_draft_and_open_me_page",
        "message/test_ios_message_browse.py::test_logged_in_user_can_browse_comment_and_interact_with_note",
        "message/test_ios_message_browse.py::test_user_can_view_system_message_detail",
        "message/test_ios_home_note_interactions.py::test_user_can_comment_on_first_home_note",
        "message/test_ios_home_note_interactions.py::test_user_can_like_and_favorite_second_home_note",
        "activity/test_publish_activity.py::test_user_can_publish_activity_for_review",
        "activity/test_manage_activity_session.py::test_user_can_add_activity_session_from_my_approved_activity",
        "activity/test_ios_activity_browse.py::test_user_can_filter_activities_by_cycling",
        "activity/test_ios_activity_browse.py::test_user_can_search_activities_by_title_or_location",
        "activity/test_ios_activity_browse.py::test_user_can_browse_activity_detail_fields",
        "activity/test_ios_activity_browse.py::test_user_can_open_activity_signup_form",
        "activity/test_ios_activity_browse.py::test_user_can_fill_activity_signup_identity_fields",
        "activity/test_ios_activity_browse.py::test_user_can_submit_activity_signup_to_payment_page",
        "activity/test_ios_activity_browse.py::test_user_can_view_my_activity_signup_status",
        "activity/test_ios_activity_browse.py::test_user_can_open_my_activity_signup_list",
        "activity/test_ios_activity_browse.py::test_user_can_open_my_activity_liked_list",
        "activity/test_ios_activity_browse.py::test_user_can_open_my_activity_favorite_list",
        "rental/test_rental_order.py::test_user_can_create_rental_order_and_leave_payment_unfinished",
    ]
    assert suite.pytest_args == ["--maxfail=1"]
