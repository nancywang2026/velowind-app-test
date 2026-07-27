from velowind_appium.cleanup import CleanupReport
from velowind_appium import cleanup_test_data


def test_run_cleanup_dispatches_ios_cleanup_steps(monkeypatch):
    class FakeDriver:
        def quit(self):
            events.append(("quit",))

    events = []

    monkeypatch.setattr(cleanup_test_data, "load_cleanup_config", lambda: "cleanup-config")
    monkeypatch.setattr(cleanup_test_data, "load_ios_config", lambda: "ios-config")
    monkeypatch.setattr(cleanup_test_data, "create_ios_driver", lambda config: events.append(("driver", config)) or FakeDriver())
    monkeypatch.setattr(
        cleanup_test_data,
        "cleanup_notes",
        lambda driver, cleanup_config, app_config, dry_run=False: events.append(("notes", dry_run))
        or CleanupReport("note", ["n1"], []),
    )
    monkeypatch.setattr(
        cleanup_test_data,
        "cleanup_activities",
        lambda driver, cleanup_config, app_config, dry_run=False: events.append(("activities", dry_run))
        or CleanupReport("activity", [], ["a1"]),
    )
    monkeypatch.setattr(cleanup_test_data, "cleanup_sessions", lambda *args, **kwargs: CleanupReport("session", [], []))

    reports = cleanup_test_data.run_cleanup("ios", include=("notes", "activities"), dry_run=True)

    assert reports == [
        CleanupReport("note", ["n1"], []),
        CleanupReport("activity", [], ["a1"]),
    ]
    assert events == [("driver", "ios-config"), ("notes", True), ("activities", True), ("quit",)]


def test_main_rejects_unknown_platform():
    assert cleanup_test_data.main(["--platform", "windows"]) == 2
