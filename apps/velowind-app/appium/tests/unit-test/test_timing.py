from velowind_appium.timing import env_flag_enabled, profile_section


def test_env_flag_enabled_accepts_common_true_values(monkeypatch):
    monkeypatch.setenv("VW_APPIUM_PROFILE", "yes")

    assert env_flag_enabled("VW_APPIUM_PROFILE") is True


def test_env_flag_enabled_is_false_for_missing_or_disabled_values(monkeypatch):
    monkeypatch.delenv("VW_APPIUM_PROFILE", raising=False)
    assert env_flag_enabled("VW_APPIUM_PROFILE") is False

    monkeypatch.setenv("VW_APPIUM_PROFILE", "false")
    assert env_flag_enabled("VW_APPIUM_PROFILE") is False


def test_profile_section_emits_duration_when_enabled():
    emitted = []
    ticks = iter([10.0, 12.345])

    with profile_section("driver.create", enabled=True, emit=emitted.append, clock=lambda: next(ticks)):
        pass

    assert emitted == ["[appium-profile] driver.create 2.35s"]


def test_profile_section_is_quiet_when_disabled():
    emitted = []

    with profile_section("driver.create", enabled=False, emit=emitted.append):
        pass

    assert emitted == []
