from types import SimpleNamespace

from velowind_appium import preflight


def _config(tmp_path):
    return SimpleNamespace(
        xcode_org_id="TEAMID",
        updated_wda_bundle_id="com.example.WebDriverAgentRunner",
        xcode_signing_id="Apple Development",
        udid="DEVICE-001",
        platform_version="26.5",
        allow_provisioning_device_registration=False,
        artifact_dir=tmp_path,
    )


def test_wda_build_preflight_skips_by_default_to_reuse_installed_wda(tmp_path, monkeypatch):
    calls = []
    wda_project = tmp_path / "WebDriverAgent.xcodeproj"
    wda_project.mkdir()

    monkeypatch.delenv("VW_IOS_SKIP_WDA_PREFLIGHT", raising=False)
    monkeypatch.setattr(preflight, "WDA_PROJECT", wda_project)
    monkeypatch.setattr(preflight.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert preflight._run_wda_build_preflight(_config(tmp_path)) == 0
    assert calls == []


def test_wda_build_preflight_can_be_enabled_explicitly(tmp_path, monkeypatch):
    calls = []
    wda_project = tmp_path / "WebDriverAgent.xcodeproj"
    wda_project.mkdir()

    monkeypatch.setenv("VW_IOS_SKIP_WDA_PREFLIGHT", "false")
    monkeypatch.setattr(preflight, "WDA_PROJECT", wda_project)

    def fake_run(command, check, capture_output, text, timeout):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert preflight._run_wda_build_preflight(_config(tmp_path)) == 0
    assert calls
