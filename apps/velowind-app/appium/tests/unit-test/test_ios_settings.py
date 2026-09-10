import pytest
from velowind_appium.ios_settings import ios_media_idle_wait


@pytest.mark.parametrize('fail', [False, True])
@pytest.mark.parametrize('initial', [0.2, 1.0, 2.0])
def test_media_idle_wait_restores_on_success_and_failure(initial, fail):
    class Driver:
        capabilities = {'platformName': 'iOS'}
        settings = {'waitForIdleTimeout': initial}
        def get_settings(self):
            return self.settings.copy()
        def update_settings(self, settings):
            self.settings.update(settings)
    driver = Driver()
    try:
        with ios_media_idle_wait(driver):
            assert driver.settings['waitForIdleTimeout'] == max(1.0, initial)
            if fail:
                raise ValueError('original error')
    except ValueError as error:
        assert fail and str(error) == 'original error'
    assert driver.settings['waitForIdleTimeout'] == initial


def test_media_idle_wait_leaves_android_alone():
    class Driver:
        capabilities = {'platformName': 'Android'}
    with ios_media_idle_wait(Driver()):
        pass


@pytest.mark.parametrize('key', ['waitForIdleTimeout', 'appium:waitForIdleTimeout'])
def test_media_idle_wait_reads_initial_capability_when_settings_omit_it(key):
    class Driver:
        capabilities = {'platformName': 'iOS', key: 0.2}
        settings = {}
        def get_settings(self):
            return self.settings.copy()
        def update_settings(self, settings):
            self.settings.update(settings)
    driver = Driver()
    with ios_media_idle_wait(driver):
        assert driver.settings['waitForIdleTimeout'] == 1.0
    assert driver.settings['waitForIdleTimeout'] == 0.2
