import pytest

from velowind_appium.android_settings import without_android_idle_wait


@pytest.mark.parametrize('fail', [False, True])
def test_restores_exact_setting_after_success_or_failure(fail):
    class Driver:
        capabilities = {'platformName': 'Android'}
        settings = {'waitForIdleTimeout': 1500, 'other': 7}
        def get_settings(self):
            return self.settings.copy()
        def update_settings(self, values):
            self.settings.update(values)
    driver = Driver()
    try:
        with without_android_idle_wait(driver):
            assert driver.settings == {'waitForIdleTimeout': 0, 'other': 7}
            if fail:
                raise ValueError('failed UI action')
    except ValueError:
        assert fail
    assert driver.settings == {'waitForIdleTimeout': 1500, 'other': 7}


def test_ios_never_accesses_android_settings():
    with without_android_idle_wait(type('Driver', (), {'capabilities': {'platformName': 'iOS'}})()):
        pass
