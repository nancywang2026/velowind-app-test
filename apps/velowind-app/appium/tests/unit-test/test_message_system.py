from pathlib import Path
from unittest.mock import Mock
import ast
import json
import pytest
from appium.webdriver.common.appiumby import AppiumBy
from velowind_appium.message_system.config import ConfigurationError, Locators, TestData, load_yaml, resolve
from velowind_appium.message_system.bridge import BridgeError, MessageBridge
from velowind_appium.message_system.ui import MessageUI
from velowind_appium.message_system.flows import MessageFlows


def test_data_has_thirteen_cases_and_independent_copies():
    data = TestData()
    assert sum(len(next(iter(c.get('parameters', {}).values()), ['default'])) for c in data.raw['scenarios'].values()) == 13
    case = data.case('MSG-A02')
    case['setup'].clear()
    assert data.case('MSG-A02')['setup']


@pytest.mark.parametrize('value', ['${missing}', '${runtime.id.x}', '${x[0]}', '${x'])
def test_unresolved_data_blocks(value):
    with pytest.raises(ConfigurationError):
        resolve(value, {'runtime': {'id': '123'}})


def test_resolution_preserves_types():
    assert resolve({'a': '${flag}', 'b': '消息-${runtime.id}'}, {'flag': False, 'runtime': {'id': '123'}}) == {'a': False, 'b': '消息-123'}


def test_duplicate_yaml_keys_fail(tmp_path):
    file = tmp_path / 'bad.yaml'
    file.write_text('a: 1\na: 2\n')
    with pytest.raises(ConfigurationError, match='Duplicate'):
        load_yaml(file)


def test_locator_strategy_and_parameters():
    locators = Locators()
    driver = Mock()
    MessageUI(driver, locators, TestData().execution).elements('conversation.row', id='entity123')
    driver.find_elements.assert_called_once_with(AppiumBy.ACCESSIBILITY_ID, 'message.conversation.entity123')
    with pytest.raises(ConfigurationError):
        locators.get('conversation.row')
    with pytest.raises(ConfigurationError):
        locators.get('unknown')


def test_rejects_xpath(tmp_path):
    file = tmp_path / 'ids.yaml'
    file.write_text('schema_version: 1\nstrategy: xpath\nids: {a: b}\n')
    with pytest.raises(ConfigurationError):
        Locators(file)


def test_literal_locator_coverage_and_single_accessibility_lookup():
    root = Path(__file__).resolve().parents[2] / 'velowind_appium/message_system'
    locators = Locators()
    methods = {'click', 'text', 'expect_text', 'element', 'optional', 'elements', 'input', 'toggle', 'set_toggle'}
    for file in (root / 'flows.py', root / 'ui.py'):
        for node in ast.walk(ast.parse(file.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in methods and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert arg.value in locators.ids, f'{file.name}: {arg.value}'
    nodes = [n for n in ast.walk(ast.parse((root / 'ui.py').read_text())) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('find_element', 'find_elements')]
    assert len(nodes) == 1
    assert ast.unparse(nodes[0].args[0]) == 'AppiumBy.ACCESSIBILITY_ID'


@pytest.mark.parametrize('ids,total,error', [(['one'], '2', 'Incomplete'), (['same', 'same'], '2', 'Duplicate')])
def test_incomplete_and_duplicate_lists_fail(ids, total, error):
    ui = MessageUI(Mock(), Locators(), {**TestData().execution, 'max_scrolls': 1})
    ui.element = Mock()
    ui.text = Mock(return_value=total)
    rows = []
    for identity in ids:
        row = Mock()
        row.get_attribute.return_value = identity
        rows.append(row)
    ui.elements = Mock(return_value=rows)
    ui.optional = Mock(return_value=Mock())
    with pytest.raises(AssertionError, match=error):
        ui.collection('home_conversations')


def make_bridge():
    return MessageBridge('http://localhost/test', 'secret', TestData().execution, 'run', 'case', 'variant')


def test_bridge_protocol_and_cleanup():
    b = make_bridge()
    response = Mock()
    response.read.return_value = json.dumps({'ok': True, 'data': {'remaining_ids': []}}).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    b.opener = Mock()
    b.opener.open.return_value = response
    b.cleanup()
    body = json.loads(b.opener.open.call_args.args[0].data)
    assert body['operation'] == 'cleanup' and body['run_id'] == 'run'
    response.read.return_value = json.dumps({'ok': True, 'data': {'remaining_ids': ['leaked']}}).encode()
    with pytest.raises(BridgeError, match='resource registry'):
        b.cleanup()


def test_mutations_not_retried():
    b = make_bridge()
    b.opener = Mock()
    b.opener.open.side_effect = TimeoutError('private details')
    with pytest.raises(BridgeError) as error:
        b.call('send')
    assert 'private' not in str(error.value) and 'secret' not in str(error.value)
    assert b.opener.open.call_count == 1


@pytest.mark.parametrize('url', ['file:///tmp/x', 'https://user:secret@host/', 'https://host/?token=secret'])
def test_invalid_endpoint(url):
    with pytest.raises(BridgeError):
        MessageBridge(url, 'secret', TestData().execution, 'run', 'case', 'variant')


def make_flow(case_id, variant='default'):
    runtime = {k: {'id': k} for k in ('actor', 'peer', 'owner', 'C', 'D', 'M0', 'N1', 'N2', 'N3', 'I1', 'I2', 'G', 'R', 'G1', 'G2', 'G3')}
    result = MessageFlows(Mock(), Mock(), TestData(), case_id, runtime, {'run_id': 'run', 'case_id': case_id, 'short_id': 'abcdef'}, variant)
    def wait(query, predicate, description):
        value = query()
        assert predicate(value)
        return value
    result.bridge.wait.side_effect = wait
    return result


def test_hidden_reappearance_fails_after_sync():
    f = make_flow('MSG-A02')
    f.ui.collection.side_effect = [{'C'}, {'C'}]
    f.bridge.call.return_value = {'id': 'incoming'}
    f.bridge.read.side_effect = [{'hidden': True}, {'synchronized_user_ids': ['actor']}, {'hidden': True}]
    with pytest.raises(AssertionError):
        f.hidden()
    assert f.bridge.read.call_args_list[1].args == ('delivery', 'incoming')


def test_denied_permission_with_side_effect_fails():
    f = make_flow('MSG-A06', 'edit_visibility')
    f.ui.collection.return_value = set()
    f.bridge.call.return_value = {'allowed': False}
    f.bridge.read.side_effect = [{'public': False}, {'public': True}]
    with pytest.raises(AssertionError, match='modified'):
        f.permissions()


def test_mark_all_read_fails():
    f = make_flow('MSG-A01')
    f.bridge.read.side_effect = [{'system': 3, 'interaction': 2}, {'read': True}]
    with pytest.raises(AssertionError):
        f.notification()


@pytest.mark.parametrize('failure_stage', ['prepare', 'body', 'none'])
def test_resource_cleanup_runs_on_all_paths(failure_stage):
    b = make_bridge()
    b.call = Mock(return_value={'runtime': {}})
    b.cleanup = Mock()
    if failure_stage == 'prepare':
        b.call.side_effect = BridgeError('prepare timed out')
    try:
        with b.prepared(setup={}):
            if failure_stage == 'body':
                raise AssertionError('business assertion')
    except (BridgeError, AssertionError):
        assert failure_stage != 'none'
    b.cleanup.assert_called_once_with()


def test_cleanup_failure_is_not_swallowed():
    b = make_bridge()
    b.call = Mock(return_value={'runtime': {}})
    b.cleanup = Mock(side_effect=BridgeError('cleanup failed'))
    with pytest.raises(BridgeError, match='cleanup failed'):
        with b.prepared(setup={}):
            pass
