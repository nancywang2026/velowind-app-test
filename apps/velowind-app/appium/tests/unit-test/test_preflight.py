from types import SimpleNamespace

from velowind_appium import preflight


def _config(tmp_path):
    return SimpleNamespace(
        xcode_org_id="TEAMID",
        updated_wda_bundle_id="com.example.WebDriverAgentRunner",
        xcode_signing_id="Apple Development",
        udid="DEVICE-001",
        server_url="http://127.0.0.1:4723",
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


def test_appium_port_env_check_rejects_mixed_listener_configuration(monkeypatch):
    def fake_run(command, check, capture_output, text, timeout):
        if command[:4] == ["lsof", "-nP", "-iTCP:4723", "-sTCP:LISTEN"]:
            return SimpleNamespace(stdout="101\n202\n")
        if command == ["ps", "eww", "-p", "101"]:
            return SimpleNamespace(stdout="node appium server APPIUM_XCUITEST_PREFER_DEVICECTL=1")
        if command == ["ps", "eww", "-p", "202"]:
            return SimpleNamespace(stdout="node appium --log-timestamp")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert not preflight._listening_appium_process_has_env(
        4723,
        "APPIUM_XCUITEST_PREFER_DEVICECTL",
        "1",
    )


def test_real_device_transport_preflight_allows_legacy_device_discovery(tmp_path, monkeypatch, capsys):
    config = _config(tmp_path)
    config.server_url = "http://127.0.0.1:4725"
    config.target = "device"

    monkeypatch.delenv("APPIUM_XCUITEST_PREFER_DEVICECTL", raising=False)
    monkeypatch.setattr(preflight, "_listening_appium_process_has_env", lambda *args, **kwargs: False)

    assert preflight._run_real_device_transport_preflight(config) == 0

    output = capsys.readouterr().out
    assert "legacy connected-device discovery" in output
    assert "4725" in output
