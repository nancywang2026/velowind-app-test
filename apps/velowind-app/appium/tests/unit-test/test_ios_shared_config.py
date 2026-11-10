import pytest
import yaml

from velowind_appium import config, cleanup_config, environment_login


@pytest.fixture
def configurations(tmp_path, monkeypatch):
    for name in ("VW_APPIUM_CONFIG_FILE", "VW_APPIUM_CLEANUP_CONFIG_FILE",
                 "VW_API_ENV", "VW_LOGIN_USERNAME", "VW_LOGIN_PASSWORD",
                 "VW_NOTE_CLEANUP_MODE", "VW_NOTE_CLEANUP_API_BASE_URL",
                 "VW_APPIUM_ENVIRONMENT_ACCOUNTS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "ios")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "ios-appium.yaml")
    for filename, account, mode in (
        ("ios-appium.yaml", "default", "ui"),
        ("ios-appium.prod.yaml", "production", "api"),
        ("custom.yaml", "custom", "ui"),
    ):
        (tmp_path / filename).write_text(yaml.safe_dump({
            "login": {"username": account, "password": account + "-password"},
            "cleanup": {"note_cleanup_mode": mode, "note_matchers": [account],
                        "delete_published_note_after_success": mode == "api"},
        }))
    return tmp_path


@pytest.mark.parametrize("environment,filename,account,mode", [
    (None, "ios-appium.yaml", "default", "ui"),
    ("test", "ios-appium.yaml", "default", "ui"),
    ("uat", "ios-appium.yaml", "default", "ui"),
    (" PROD ", "ios-appium.prod.yaml", "production", "api"),
])
def test_login_and_cleanup_select_same_environment_file(
        configurations, monkeypatch, environment, filename, account, mode):
    if environment is not None:
        monkeypatch.setenv("VW_API_ENV", environment)
    assert config.resolve_ios_config_file() == configurations / filename
    assert config.load_ios_config().login_username == account
    assert cleanup_config.load_cleanup_config().note_matchers == [account]
    assert cleanup_config.note_cleanup_mode() == mode


def test_explicit_shared_file_overrides_prod_and_field_overrides_remain(configurations, monkeypatch):
    monkeypatch.setenv("VW_API_ENV", "prod")
    monkeypatch.setenv("VW_APPIUM_CONFIG_FILE", str(configurations / "custom.yaml"))
    assert config.load_ios_config().login_username == "custom"
    assert cleanup_config.load_cleanup_config().note_matchers == ["custom"]
    monkeypatch.setenv("VW_LOGIN_USERNAME", "override")
    monkeypatch.setenv("VW_LOGIN_PASSWORD", "override-password")
    monkeypatch.setenv("VW_NOTE_CLEANUP_MODE", "api")
    monkeypatch.setenv("VW_NOTE_CLEANUP_API_BASE_URL", "https://override.example")
    loaded = config.load_ios_config()
    assert (loaded.login_username, loaded.login_password) == ("override", "override-password")
    assert cleanup_config.note_cleanup_mode() == "api"
    assert cleanup_config.note_cleanup_api_base_url() == "https://override.example/api/v1/mobile"


def test_missing_production_file_does_not_fall_back_to_default_account(configurations, monkeypatch):
    monkeypatch.setenv("VW_API_ENV", "prod")
    (configurations / "ios-appium.prod.yaml").unlink()
    for load in (config.load_ios_config, cleanup_config.load_cleanup_config):
        with pytest.raises(FileNotFoundError, match="Production Appium configuration"):
            load()


def test_conflicting_cleanup_override_is_rejected(configurations, monkeypatch):
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", str(configurations / "custom.yaml"))
    for load in (config.load_ios_config, cleanup_config.load_cleanup_config):
        with pytest.raises(ValueError, match="same VW_APPIUM_CONFIG_FILE"):
            load()
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", str(configurations / "ios-appium.yaml"))
    assert cleanup_config.load_cleanup_config().note_matchers == ["default"]


def test_ios_does_not_implicitly_switch_accounts_using_private_manifest(configurations, monkeypatch):
    monkeypatch.setenv("VW_API_ENV", "prod")
    manifest = configurations / "private-manifest.yaml"
    manifest.write_text("invalid: manifest")
    monkeypatch.setattr(environment_login, "DEFAULT_ENVIRONMENT_ACCOUNTS", manifest)
    assert environment_login.load_environment_accounts() is None
    assert config.load_ios_config().login_username == "production"


def test_android_retains_legacy_cleanup_file(configurations, monkeypatch):
    monkeypatch.setenv("VW_APPIUM_PLATFORM", "android")
    monkeypatch.setenv("VW_APPIUM_CLEANUP_CONFIG_FILE", str(configurations / "custom.yaml"))
    assert cleanup_config.load_cleanup_config().note_matchers == ["custom"]
