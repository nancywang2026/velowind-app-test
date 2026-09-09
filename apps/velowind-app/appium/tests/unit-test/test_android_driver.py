from velowind_appium.android_driver import install_android_script_compatibility


def test_android_driver_translates_mobile_tap_to_click_gesture():
    calls = []

    class FakeDriver:
        def execute_script(self, script, payload=None):
            calls.append((script, payload))
            return "ok"

    driver = FakeDriver()
    install_android_script_compatibility(driver)

    assert driver.execute_script("mobile: tap", {"x": 900, "y": 260}) == "ok"
    assert calls == [("mobile: clickGesture", {"x": 900, "y": 260})]


def test_android_driver_translates_directional_swipe_to_swipe_gesture():
    calls = []

    class FakeDriver:
        @staticmethod
        def get_window_rect():
            return {"width": 1080, "height": 2400}

        def execute_script(self, script, payload=None):
            calls.append((script, payload))
            return "ok"

    driver = FakeDriver()
    install_android_script_compatibility(driver)

    assert driver.execute_script("mobile: swipe", {"direction": "up"}) == "ok"
    assert calls == [
        (
            "mobile: swipeGesture",
            {"left": 108, "top": 480, "width": 864, "height": 1440, "direction": "up", "percent": 0.75},
        )
    ]


def test_android_driver_bounds_idle_wait_and_keeps_implicit_wait_disabled(monkeypatch):
    from velowind_appium import android_driver
    calls = []
    class Driver:
        def update_settings(self, values): calls.append(('settings', values))
        def implicitly_wait(self, seconds): calls.append(('implicit', seconds))
        def execute_script(self, *args): pass
    driver = Driver()
    monkeypatch.delenv('VW_ANDROID_WAIT_FOR_IDLE_TIMEOUT_MS', raising=False)
    monkeypatch.setattr(android_driver, 'build_android_capabilities', lambda config: {})
    monkeypatch.setattr(android_driver.webdriver, 'Remote', lambda **kwargs: driver)
    config = type('Config', (), {'server_url': 'http://localhost:4725'})()
    assert android_driver.create_android_driver(config) is driver
    assert calls == [('settings', {'waitForIdleTimeout': 1000}), ('implicit', 0)]


def test_android_driver_validates_timeout_before_creating_session(monkeypatch):
    import pytest
    from velowind_appium import android_driver
    monkeypatch.setenv('VW_ANDROID_WAIT_FOR_IDLE_TIMEOUT_MS', '-1')
    monkeypatch.setattr(android_driver.webdriver, 'Remote', lambda **kwargs: pytest.fail('must validate before launch'))
    with pytest.raises(ValueError):
        android_driver.create_android_driver(object())


def test_android_driver_closes_session_when_settings_fail(monkeypatch):
    import pytest
    from velowind_appium import android_driver
    calls = []
    class Driver:
        def update_settings(self, values): raise RuntimeError('settings unavailable')
        def quit(self): calls.append('quit')
    monkeypatch.setattr(android_driver, 'build_android_capabilities', lambda config: {})
    monkeypatch.setattr(android_driver.webdriver, 'Remote', lambda **kwargs: Driver())
    with pytest.raises(RuntimeError, match='settings unavailable'):
        android_driver.create_android_driver(type('Config', (), {'server_url': 'http://localhost:4725'})())
    assert calls == ['quit']
