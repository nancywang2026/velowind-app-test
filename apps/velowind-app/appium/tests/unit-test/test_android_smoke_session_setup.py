from pathlib import Path

import pytest

from tests.android_smoke import conftest as android_smoke_conftest


def test_android_smoke_logged_in_session_logs_in_before_case(monkeypatch):
    driver = object()
    config = object()
    calls = []

    def fake_prepare_logged_in_session(received_driver, received_config):
        calls.append(("login", received_driver, received_config))
        return True

    monkeypatch.setattr(
        android_smoke_conftest,
        "prepare_logged_in_session",
        fake_prepare_logged_in_session,
    )

    fixture = android_smoke_conftest.logged_in_session.__wrapped__(driver, config, lambda *args, **kwargs: None, object())
    next(fixture)

    assert calls == [("login", driver, config)]

    try:
        next(fixture)
    except StopIteration:
        pass


def test_prepare_logged_in_session_checks_me_tab_before_home(monkeypatch):
    driver = object()
    config = object()
    calls = []

    monkeypatch.setattr(
        android_smoke_conftest,
        "ensure_logged_in_from_me_then_home",
        lambda received_driver, received_config: calls.append((received_driver, received_config)) or True,
    )

    assert android_smoke_conftest.prepare_logged_in_session(driver, config) is True
    assert calls == [(driver, config)]


def test_android_smoke_logged_in_session_restores_after_case_with_env(monkeypatch):
    driver = object()
    config = object()
    calls = []

    monkeypatch.setenv("VW_APPIUM_RESTORE_HOME_AFTER_CASE", "true")
    monkeypatch.setattr(
        android_smoke_conftest,
        "prepare_logged_in_session",
        lambda received_driver, received_config: calls.append((received_driver, received_config)),
    )

    fixture = android_smoke_conftest.logged_in_session.__wrapped__(
        driver,
        config,
        lambda *args, **kwargs: None,
        object(),
    )
    next(fixture)
    with pytest.raises(StopIteration):
        next(fixture)

    assert calls == [(driver, config), (driver, config)]


def test_android_smoke_logged_in_session_restores_after_case_with_marker(monkeypatch):
    driver = object()
    config = object()
    calls = []

    class DummyNode:
        @staticmethod
        def get_closest_marker(name):
            return object() if name == "restore_home_after" else None

    class DummyRequest:
        node = DummyNode()

    monkeypatch.setattr(
        android_smoke_conftest,
        "prepare_logged_in_session",
        lambda received_driver, received_config: calls.append((received_driver, received_config)),
    )

    fixture = android_smoke_conftest.logged_in_session.__wrapped__(
        driver,
        config,
        lambda *args, **kwargs: None,
        DummyRequest(),
    )
    next(fixture)
    with pytest.raises(StopIteration):
        next(fixture)

    assert calls == [(driver, config), (driver, config)]


def test_android_smoke_skips_final_page_for_passed_test_by_default(monkeypatch):
    captured = []

    class DummyOutcome:
        @staticmethod
        def get_result():
            class Report:
                when = "call"
                passed = True
                outcome = "passed"

            return Report()

    class DummyItem:
        funcargs = {
            "android_driver": object(),
            "android_config": type("Config", (), {"artifact_dir": Path(".tmp/appium-android")})(),
        }
        name = "test_demo"
        nodeid = "android_smoke/test_demo.py::test_demo"

    class StepContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(android_smoke_conftest.allure, "step", lambda title: captured.append(("step", title)) or StepContext())
    monkeypatch.setattr(
        android_smoke_conftest,
        "capture_and_attach_page",
        lambda driver, artifact_dir, label: captured.append(("capture", label, artifact_dir)),
    )

    hook = android_smoke_conftest.pytest_runtest_makereport(DummyItem(), None)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(DummyOutcome())

    assert captured == []


def test_android_smoke_can_capture_final_page_for_passed_test(monkeypatch):
    captured = []

    class DummyOutcome:
        @staticmethod
        def get_result():
            class Report:
                when = "call"
                passed = True
                outcome = "passed"

            return Report()

    class DummyItem:
        funcargs = {
            "android_driver": object(),
            "android_config": type("Config", (), {"artifact_dir": Path(".tmp/appium-android")})(),
        }
        name = "test_demo"
        nodeid = "android_smoke/test_demo.py::test_demo"

    class StepContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setenv("VW_APPIUM_CAPTURE_FINAL_PAGE_ON_PASS", "true")
    monkeypatch.setattr(android_smoke_conftest.allure, "step", lambda title: captured.append(("step", title)) or StepContext())
    monkeypatch.setattr(
        android_smoke_conftest,
        "capture_and_attach_page",
        lambda driver, artifact_dir, label: captured.append(("capture", label, artifact_dir)),
    )

    hook = android_smoke_conftest.pytest_runtest_makereport(DummyItem(), None)
    next(hook)
    with pytest.raises(StopIteration):
        hook.send(DummyOutcome())

    assert captured == [
        ("step", "final-page"),
        ("capture", "test_demo-final-page", Path(".tmp/appium-android")),
    ]
