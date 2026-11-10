from pathlib import Path

import pytest
import yaml

from velowind_appium import android_config, environment_login


@pytest.fixture
def configs(tmp_path, monkeypatch):
    for key in ['VW_APPIUM_CONFIG_FILE', 'VW_API_ENV', 'VW_LOGIN_USERNAME', 'VW_LOGIN_PASSWORD',
                'VW_APPIUM_ENVIRONMENT_ACCOUNTS']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('VW_APPIUM_PLATFORM', 'android')
    monkeypatch.setattr(android_config, 'DEFAULT_CONFIG_FILE', tmp_path / 'android-appium.yaml')
    monkeypatch.setattr(android_config, 'auto_detect_online_android_udid', lambda *args: None)
    for name, account in [('android-appium.yaml', 'ordinary'), ('android-appium.prod.yaml', 'production'), ('custom.yaml', 'custom')]:
        (tmp_path / name).write_text(yaml.safe_dump({'login': {'username': account, 'password': account + '-password'}}))
    return tmp_path


@pytest.mark.parametrize('env,expected', [(None,'ordinary'),('test','ordinary'),('uat','ordinary'),('prod','production'),(' PROD ','production')])
def test_android_selects_environment_credentials(configs, monkeypatch, env, expected):
    if env is not None:
        monkeypatch.setenv('VW_API_ENV', env)
    c=android_config.load_android_config()
    assert (c.login_username,c.login_password)==(expected,expected+'-password')


def test_production_missing_file_does_not_use_ordinary_password(configs, monkeypatch):
    monkeypatch.setenv('VW_API_ENV','prod')
    (configs/'android-appium.prod.yaml').unlink()
    with pytest.raises(FileNotFoundError, match='Production Android'):
        android_config.load_android_config()


def test_explicit_file_and_credentials_keep_precedence(configs, monkeypatch):
    monkeypatch.setenv('VW_API_ENV','prod')
    monkeypatch.setenv('VW_APPIUM_CONFIG_FILE',str(configs/'custom.yaml'))
    assert android_config.load_android_config().login_username=='custom'
    monkeypatch.setenv('VW_LOGIN_USERNAME','override')
    monkeypatch.setenv('VW_LOGIN_PASSWORD','override-password')
    assert android_config.load_android_config().login_password=='override-password'


def test_android_prod_does_not_implicitly_use_other_account_manifest(configs, monkeypatch):
    monkeypatch.setenv('VW_API_ENV','prod')
    manifest=configs/'unrelated.yaml';manifest.write_text('not: valid')
    monkeypatch.setattr(environment_login,'DEFAULT_ENVIRONMENT_ACCOUNTS',manifest)
    monkeypatch.setattr(environment_login,'_read_yaml_config',lambda: pytest.fail('must not read iOS YAML'))
    assert environment_login.load_environment_accounts() is None
    assert android_config.load_android_config().login_username=='production'


def test_android_local_script_does_not_override_yaml_credentials():
    script=Path(__file__).resolve().parents[5]/'scripts/appium-android-local.sh'
    text=script.read_text()
    assert 'export VW_LOGIN_USERNAME=' not in text
    assert 'export VW_LOGIN_PASSWORD=' not in text
