"""Explicit opt-in; preflight before login, device creation, or data mutations."""
import json
import os
from pathlib import Path
import uuid
import subprocess
from urllib.request import urlopen
from dataclasses import replace
import pytest

from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver
from velowind_appium.message_regression.config import read_configuration
from velowind_appium.message_regression.core import API, Blocked
from velowind_appium.message_regression.native import NativeUI
from velowind_appium.message_regression.program import Program


@pytest.fixture(autouse=True)
def logged_in_session():
    # Override parent navigation/login so disabled/blocked cases touch no device.
    yield


@pytest.fixture
def regression_program(request, message_case):
    if os.getenv("VW_MESSAGE_REGRESSION") != "1":
        pytest.skip("BLOCKED: enable VW_MESSAGE_REGRESSION=1 after configuring real execution bindings")
    if os.getenv("PYTEST_XDIST_WORKER"):
        pytest.fail("Message UI suite requires serial device access")
    try:
        data, accounts = read_configuration()
        case, _ = message_case
        from velowind_appium.message_regression.config import audit_bindings
        audit = audit_bindings(data, [case])[0]
        if audit["missing_operations"]:
            raise Blocked("Missing execution operations: " + ", ".join(audit["missing_operations"]))
        if case.conditional and case.conditional not in data.get("capabilities", []):
            raise Blocked("Missing prerequisite: " + case.conditional)
        # Every UI role gets its own explicitly configured device; never replace
        # another account's session on the same UDID. Account switching needs a
        # verified adapter instead of pretending all roles share one identity.
        devices = data.get("devices", {})
        required_roles = {step["actor"] for name in ("prepare."+case.id,*case.operations,"cleanup."+case.id)
                          for step in data["operations"][name]["steps"] if step.get("kind") == "ui"}
        if not required_roles: raise Blocked("At least one native UI observation is required for an Appium journey")
        if any(role not in devices for role in required_roles): raise Blocked("Missing explicitly owned UI device per actor")
        udids = [devices[role].get("udid") for role in required_roles]
        if not all(udids) or len(udids) != len(set(udids)):
            raise Blocked("UI actors require distinct owned devices; no automatic account/session replacement")
        processes = subprocess.run(["ps","-axo","pid=,command="],capture_output=True,text=True,check=True).stdout
        competing = [line for line in processes.splitlines() if "python" in line and " -m pytest " in line
                     and line.strip().split(None,1)[0] != str(os.getpid())]
        if competing: raise Blocked("Another pytest process is running; do not compete for the device")
        api = API(data["api_origin"])
        report = []
        program = Program(api, {role:None for role in accounts}, {}, data["operations"], {"run_id":uuid.uuid4().hex}, report)
        for role in required_roles:
            device = devices[role]
            if device.get("owned_by_this_run") is not True:
                raise Blocked("Explicit per-device ownership declaration required")
            if not device.get("identity_locator") or not device.get("identity_evidence"):
                raise Blocked("Verified UI account identity locator required")
            if not device.get("server_url", "").startswith("http://127.0.0.1:"):
                raise Blocked("Explicit local Appium server_url required")
            try:
                with urlopen(device["server_url"] + "/sessions", timeout=5) as response:
                    existing = json.load(response).get("value")
            except Exception:
                raise Blocked("Cannot inspect Appium session ownership") from None
            if existing != []: raise Blocked("Appium server already has a session; do not replace another run")
        # Validate native locator bindings before any login/data write.
        probe_uis = {role:NativeUI(None, data.get("locators", {})) for role in required_roles}
        program.uis = probe_uis
        program.preflight(("prepare."+case.id,*case.operations,"cleanup."+case.id))
    except Blocked as exc:
        pytest.skip("BLOCKED: " + str(exc))
    actors = {role:api.login(account["phone"], account["password"], expected_id=account["user_id"], name=account["name"])
              for role,account in accounts.items()}
    program.actors = actors
    program.context["actors"] = {role:{"id":actor.user_id,"name":actor.name} for role,actor in actors.items()}
    drivers = []
    try:
        for role in required_roles:
            device = devices[role]
            config = replace(load_ios_config(), udid=device["udid"], server_url=device["server_url"],
                             wda_local_port=device.get("wda_local_port"), no_reset=True)
            driver = create_ios_driver(config); drivers.append(driver)
            ui = NativeUI(driver, data.get("locators", {}))
            actual = ui.action("value", device["identity_locator"])
            if actual != actors[role].user_id: raise Blocked("Device not logged into expected test identity")
            program.uis[role] = ui
        yield program, data.get("capabilities", [])
    finally:
        # Journal contains method/path/status only, never credentials or raw responses.
        output = Path(data.get("report_directory", ".tmp/message-regression")) / program.context["run_id"]
        output.mkdir(parents=True, exist_ok=True)
        (output/"execution.json").write_text(json.dumps({"steps":report, "api":api.journal,
            "cleanup_errors":program.context.get("cleanup_errors",[])},ensure_ascii=False,indent=2))
        for driver in reversed(drivers): driver.quit()
        if program.context.get("cleanup_errors"):
            pytest.fail("cleanup-pending: original assertion result preserved; inspect execution.json")
