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


def test_load_android_test_suite_supports_file_methods(tmp_path):
    suite_file = tmp_path / "suite.yaml"
    suite_file.write_text(
        """
tests:
  - file: android_smoke/test_android_feature_walkthrough.py
    methods:
      - test_android_home_categories_are_reachable
      - test_android_bottom_tabs_are_reachable
  - message/test_ios_publish_note.py
pytest_args:
  - --maxfail=1
""".strip(),
        encoding="utf-8",
    )

    suite = run_android_tests.load_test_suite(suite_file)

    assert suite.tests == [
        "android_smoke/test_android_feature_walkthrough.py::test_android_home_categories_are_reachable",
        "android_smoke/test_android_feature_walkthrough.py::test_android_bottom_tabs_are_reachable",
        "message/test_ios_publish_note.py",
    ]
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


def test_build_android_pytest_command_uses_isolated_allure_run_dir(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_RUN_ID", "android-run-1")

    command = run_android_tests.build_pytest_command(["-m", "android_smoke"])

    assert f"--alluredir={run_android_tests.REPO_ROOT / '.tmp' / 'appium-android' / 'runs' / 'android-run-1' / 'allure-results'}" in command
    assert f"--alluredir={run_android_tests.REPO_ROOT / '.tmp' / 'appium-android' / 'allure-results'}" not in command


def test_build_android_pytest_command_allows_allure_result_dir_override(monkeypatch, tmp_path):
    results_dir = tmp_path / "custom-results"
    monkeypatch.setenv("VW_ALLURE_RESULTS_DIR", str(results_dir))

    command = run_android_tests.build_pytest_command(["-m", "android_smoke"])

    assert f"--alluredir={results_dir}" in command


def test_build_android_pytest_command_rejects_empty_suite_file(tmp_path):
    suite_file = tmp_path / "empty.yaml"
    suite_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one"):
        run_android_tests.build_pytest_command(["--suite", str(suite_file)])


def test_android_runner_uses_android_artifact_paths():
    artifacts = run_android_tests.allure_artifacts("android-run-1")

    assert artifacts.results == Path(run_android_tests.REPO_ROOT) / ".tmp" / "appium-android" / "runs" / "android-run-1" / "allure-results"
    assert artifacts.report == Path(run_android_tests.REPO_ROOT) / ".tmp" / "appium-android" / "runs" / "android-run-1" / "allure-report"


def test_android_activity_publish_suite_uses_platform_neutral_activity_case():
    suite_file = (
        Path(run_android_tests.REPO_ROOT)
        / "apps"
        / "velowind-app"
        / "appium"
        / "test-suites"
        / "android-activity-publish.yaml"
    )

    suite = run_android_tests.load_test_suite(suite_file)

    assert suite.tests == ["activity/test_publish_activity.py"]
    assert suite.pytest_args == ["--maxfail=1"]


def test_android_full_suite_contains_required_regression_cases():
    suite_file = (
        Path(run_android_tests.REPO_ROOT)
        / "apps"
        / "velowind-app"
        / "appium"
        / "test-suites"
        / "android-full.yaml"
    )

    suite = run_android_tests.load_test_suite(suite_file)

    assert suite.tests == [
        "android_smoke/test_android_feature_walkthrough.py::test_android_home_categories_are_reachable",
        "android_smoke/test_android_feature_walkthrough.py::test_android_bottom_tabs_are_reachable",
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


def test_android_runner_syncs_media_before_pytest(monkeypatch):
    calls = []

    monkeypatch.setattr(run_android_tests.sys, "argv", ["run_android_tests", "--all"])
    monkeypatch.setattr(
        run_android_tests.android_media_sync,
        "main",
        lambda: calls.append("sync") or 0,
    )
    monkeypatch.setattr(
        run_android_tests,
        "_run",
        lambda command: calls.append("pytest") or type("Result", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(run_android_tests, "_generate_and_open_report", lambda: None)

    assert run_android_tests.main() == 0
    assert calls == ["sync", "pytest"]
