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
