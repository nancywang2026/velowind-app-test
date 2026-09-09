import os
import uuid
from dataclasses import replace

import pytest

from velowind_appium.config import load_ios_config
from velowind_appium.driver import create_ios_driver
from velowind_appium.message_system.bridge import MessageBridge
from velowind_appium.message_system.config import TestData, Locators, ConfigurationError, resolve
from velowind_appium.message_system.flows import MessageFlows
from velowind_appium.message_system.ui import MessageUI


def pytest_generate_tests(metafunc):
    if 'message_case' not in metafunc.fixturenames:
        return
    data = TestData()
    cases = []
    for case_id, case in data.raw['scenarios'].items():
        parameters = case.get('parameters', {})
        if len(parameters) > 1:
            raise ConfigurationError('Only one parameter dimension per message scenario is supported')
        variants = next(iter(parameters.values()), ['default'])
        cases.extend(pytest.param((case_id, variant), id=f'{case_id}-{variant}') for variant in variants)
    metafunc.parametrize('message_case', cases)


@pytest.fixture
def ios_config():
    # Override the parent autouse configuration: opt-out must not connect a device.
    if os.getenv('VW_MESSAGE_AUTOMATION') != '1':
        pytest.skip('BLOCKED: opt in with VW_MESSAGE_AUTOMATION=1 after integrating IDs and test bridge')
    if os.getenv('PYTEST_XDIST_WORKER') or os.getenv('VW_APPIUM_PLATFORM', 'ios') != 'ios':
        raise ConfigurationError('Message suite requires serial execution on iOS')
    for name in ('MESSAGE_TEST_BRIDGE_URL', 'MESSAGE_TEST_BRIDGE_TOKEN'):
        if not os.getenv(name):
            raise ConfigurationError(f'Missing environment variable: {name}')
    config = replace(load_ios_config(), no_reset=True)
    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def message_runtime(message_case, ios_config):
    data, locators = TestData(), Locators()
    case_id, variant = message_case
    case = data.case(case_id)
    credentials = data.credentials(case['actor'])
    accounts = {}
    for role, account in data.raw['accounts'].items():
        name = account['username_env']
        if not os.getenv(name):
            raise ConfigurationError(f'Missing environment variable: {name}')
        accounts[role] = os.environ[name]
    if len(set(accounts.values())) != len(accounts):
        raise ConfigurationError('Message roles require distinct test accounts')
    run_id = uuid.uuid4().hex
    context = {'run_id': run_id, 'case_id': case_id, 'short_id': run_id[:6]}
    bridge = MessageBridge(os.environ['MESSAGE_TEST_BRIDGE_URL'], os.environ['MESSAGE_TEST_BRIDGE_TOKEN'],
                           data.execution, run_id, case_id, variant)
    # Register cleanup before prepare: a timed-out mutation can still have succeeded.
    with bridge.prepared(setup=resolve(case['setup'], context), accounts=accounts) as prepared:
        runtime = prepared['runtime']
        for role in accounts:
            if not isinstance(runtime[role]['id'], str) or not runtime[role]['id']:
                raise ConfigurationError(f'Bridge returned invalid account ID: {role}')
        yield data, locators, bridge, runtime, context, credentials


@pytest.fixture
def driver(message_runtime, ios_config):
    app_driver = create_ios_driver(ios_config)
    try:
        yield app_driver
    finally:
        app_driver.quit()


@pytest.fixture
def message_flow(driver, message_runtime, message_case):
    data, locators, bridge, runtime, context, credentials = message_runtime
    case_id, variant = message_case
    ui = MessageUI(driver, locators, data.execution)
    ui.login(*credentials, runtime[data.case(case_id)['actor']]['id'])
    return MessageFlows(ui, bridge, data, case_id, runtime, context, variant)
