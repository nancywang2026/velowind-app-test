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

    fixture = android_smoke_conftest.logged_in_session.__wrapped__(
        driver,
        config,
        lambda *args, **kwargs: None,
    )
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
