from pathlib import Path
from unittest.mock import Mock
import io
import json
import pytest

from velowind_appium.message_regression.core import API, Actor, Blocked, Resources, wait
from velowind_appium.message_regression.business import Messages
from velowind_appium.message_regression.config import audit_bindings, read_configuration
from velowind_appium.message_regression.program import Program, resolve, check
from velowind_appium.message_regression.journeys import CASES, Case, run_case
from velowind_appium.message_regression.hooks import existing_business_with_notification
from velowind_appium.message_regression.native import NativeUI


A = Actor("a-id", "A", "private-token")


def test_no_secrets_in_actor_repr():
    assert "private-token" not in repr(A)


@pytest.mark.parametrize("value", ["https://api.velowind.com", "http://dev-api.velowind.com", "https://dev-api.velowind.com.evil"])
def test_test_host_guard(value):
    with pytest.raises(Blocked): API(value)


def test_mutation_timeout_is_unknown_without_retry_or_secret_journal():
    opener = Mock(); opener.open.side_effect = TimeoutError("secret server details")
    api = API("https://dev-api.velowind.com", opener=opener)
    with pytest.raises(Exception):
        api.request(A,"POST","/api/v1/mobile/example",body={"password":"private-password"})
    assert opener.open.call_count == 1
    assert api.journal[0]["status"] == "unknown"
    assert "private" not in json.dumps(api.journal)


def test_null_mutation_data_is_valid():
    opener = Mock(); response = Mock()
    response.read.return_value=b'{"code":0,"data":null}'
    response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    opener.open.return_value=response
    assert API("https://dev-api.velowind.com",opener=opener).request(A,"DELETE","/api/v1/mobile/ugc/comments/new") is None


@pytest.mark.parametrize("responses", [
    [{"items":[{"id":"1"}],"total":2},{"items":[{"id":"1"}],"total":2}],
    [{"items":[],"total":1}],
    [{"items":[{"id":"1"}],"total":0}],
])
def test_page_duplicates_empty_intermediate_or_invalid_totals_fail(responses):
    api=API("https://dev-api.velowind.com");api.request=Mock(side_effect=responses)
    with pytest.raises(AssertionError):api.pages(A,"/api/v1/mobile/items",id_key="id")


def test_cursor_empty_middle_page_still_advances():
    api=API("https://dev-api.velowind.com");api.request=Mock(side_effect=[
        {"items":[],"hasMore":True,"nextCursor":"cursor-1"},
        {"items":[{"userId":"b"}],"hasMore":False}])
    assert api.pages(A,"/api/v1/mobile/members",id_key="userId",mode="cursor")==[{"userId":"b"}]
    assert api.request.call_args.kwargs["params"]["cursor"]=="cursor-1"


def test_stale_cursor_fails_instead_of_missing_members():
    api=API("https://dev-api.velowind.com");api.request=Mock(return_value={"items":[],"hasMore":True,"nextCursor":"same"})
    with pytest.raises(AssertionError,match="repeated"):api.pages(A,"/api/v1/mobile/members",id_key="userId",mode="cursor")


def test_notification_rejects_old_ids_and_wrong_business_target():
    service=Messages(Mock())
    service.notifications=Mock(return_value=[
        {"inboxId":"old","notificationType":"TYPE","action":{"bizId":"target"}},
        {"inboxId":"wrong","notificationType":"TYPE","action":{"bizId":"other"}},
        {"inboxId":"new","notificationType":"TYPE","action":{"bizId":"target"}}])
    service.api.request.return_value={"action":{"bizId":"target"}}
    assert service.notification_after(A,{"old"},"target","TYPE")=={"action":{"bizId":"target"}}
    assert service.api.request.call_args.args[2].endswith("/new")


def test_duplicate_notification_is_failure():
    service=Messages(Mock()); service.notifications=Mock(return_value=[
        {"inboxId":x,"notificationType":"TYPE","action":{"bizId":"target"}} for x in ["one","two"]])
    with pytest.raises(AssertionError,match="Duplicate"):service.notification_after(A,set(),"target","TYPE")


def test_history_uses_actual_forward_cursor_and_rejects_fake_full_history():
    api=Mock();api.request.side_effect=[
        {"messages":[{"messageId":"1"}],"hasMore":True,"latestReturnedMessageId":"1","resyncRequired":False},
        {"messages":[{"messageId":"2"}],"hasMore":False,"resyncRequired":False}]
    result=Messages(api).history(A,"peer",expected_ids={"1","2"})
    assert set(result)=={"1","2"}
    assert api.request.call_args.kwargs["params"]["afterMessageId"]=="1"


def test_history_missing_or_duplicate_message_cannot_pass():
    api=Mock();api.request.return_value={"messages":[{"messageId":"1"}],"hasMore":False}
    with pytest.raises(AssertionError,match="missing"):Messages(api).history(A,"peer",expected_ids={"2"})
    api.request.return_value={"messages":[{"messageId":"1"},{"messageId":"1"}],"hasMore":False}
    with pytest.raises(AssertionError,match="Duplicate"):Messages(api).history(A,"peer")


def test_templates_preserve_types_and_missing_values_block():
    assert resolve({"count":"${p.n}","text":"id-${p.id}"},{"p":{"n":3,"id":"new"}})=={"count":3,"text":"id-new"}
    with pytest.raises(Blocked):resolve("${unknown}",{})


def test_string_true_and_duplicates_do_not_pass_assertions():
    with pytest.raises(AssertionError):check("true",True)
    with pytest.raises(AssertionError):check(["a","a"],["a"],"same_set")


def test_preflight_rejects_missing_and_unknown_steps_before_mutation():
    api=Mock();p=Program(api,{}, {},{"bad":{"source":"evidence","steps":[{"kind":"shell"}]}},{},[])
    with pytest.raises(Blocked):p.preflight(["bad"])
    with pytest.raises(Blocked):p.run("missing")
    api.request.assert_not_called()


@pytest.mark.parametrize("stage",["prepare","action","assertion"])
def test_journey_cleanup_runs_on_prepare_action_and_assertion_failures(stage):
    case=Case("TEST","test",("default",),("action",),(("action.ok","eq",True),))
    program=Mock();program.context={};program.report=[]
    def run(name,**kwargs):
        if name=="prepare.TEST" and stage=="prepare":raise AssertionError("prepare failed")
        if name=="action" and stage=="action":raise AssertionError("action failed")
        if name=="action":return {"ok":False}
        if name=="cleanup.TEST":return {"remaining_ids":[],"restored":True}
        return {}
    program.run.side_effect=run
    with pytest.raises(AssertionError):run_case(case,"default",program)
    assert program.run.call_args.args[0]=="cleanup.TEST"


def test_cleanup_errors_preserved_separately_from_business_assertion():
    case=Case("TEST","test",("default",),("action",),())
    program=Mock();program.context={};program.report=[]
    def run(name,**kwargs):
        if name=="action":raise AssertionError("original business failure")
        if name=="cleanup.TEST":raise RuntimeError("cleanup failure")
        return {}
    program.run.side_effect=run
    with pytest.raises(AssertionError,match="original"):run_case(case,"default",program)
    assert program.context["cleanup_errors"]==["RuntimeError"]
    assert program.report[-1]["status"]=="cleanup-pending"


def test_missing_condition_blocks_before_data_preparation():
    case=next(c for c in CASES if c.id=="MSG-016")
    program=Mock()
    with pytest.raises(Blocked):run_case(case,case.variants[0],program)
    program.run.assert_not_called()


def test_existing_business_action_is_not_repeated_and_cleanup_follows_notification():
    events=[];hook=Mock()
    hook.before_business.side_effect=lambda:events.append("baseline")
    hook.after_business.side_effect=lambda *args:events.append("notification")
    def action():events.append("business");return {"id":"this-run"}
    existing_business_with_notification(action,hook,business_id=lambda x:x["id"],
        assert_business_success=lambda x:True,cleanup=lambda:events.append("cleanup"))
    assert events==["baseline","business","notification","cleanup"]


def test_existing_business_notification_failure_still_cleans():
    hook=Mock();hook.after_business.side_effect=AssertionError("missing notification")
    cleanup=Mock()
    with pytest.raises(AssertionError):existing_business_with_notification(lambda:42,hook,
        business_id=str,assert_business_success=lambda x:True,cleanup=cleanup)
    cleanup.assert_called_once()


def test_resources_attempt_all_cleanups_even_when_one_fails():
    resources=Resources();cleanup=Mock()
    resources.add("first",cleanup,lambda:True)
    resources.add("second",lambda:(_ for _ in ()).throw(RuntimeError()),lambda:True)
    with pytest.raises(AssertionError,match="cleanup-pending"):resources.cleanup()
    cleanup.assert_called_once()


def test_all_approved_csv_ids_have_executable_journey_definition():
    import csv,re
    path=Path("/Users/test/Nancy/Testing/document/测试/消息测试用例-10:19.csv")
    if not path.exists():pytest.skip("Local design CSV unavailable")
    with path.open(encoding="utf-8-sig",newline="") as source:rows=list(csv.reader(source))
    ids={re.match(r"(MSG-[A-Z0-9-]+)",r[9])[1] for r in rows if len(r)>9 and r[9].startswith("MSG-")}
    assert ids=={c.id for c in CASES}
    assert all(c.assertions and c.operations for c in CASES)
    assert all("hide" not in op and "join_application" not in op for c in CASES for op in c.operations)


def test_audit_reports_missing_bindings_instead_of_claiming_coverage():
    rows=audit_bindings({},CASES)
    assert all(x["status"]=="blocked" and x["missing_operations"] for x in rows)


def test_latest_message_must_be_above_input_and_inside_viewport():
    driver=Mock();driver.get_window_size.return_value={"width":400,"height":800}
    ui=NativeUI(driver,{})
    message,composer=Mock(),Mock()
    message.rect={"x":20,"y":650,"width":200,"height":100}
    composer.rect={"x":0,"y":700,"width":400,"height":100}
    ui.one=Mock(side_effect=[message,composer])
    with pytest.raises(AssertionError,match="obscured"):ui.contained_above("latest","composer")
    message.rect={"x":20,"y":600,"width":200,"height":90}
    ui.one=Mock(side_effect=[message,composer])
    ui.contained_above("latest","composer")


def test_unverified_or_ambiguous_native_locator_cannot_assert_pass():
    ui=NativeUI(Mock(),{})
    with pytest.raises(Blocked):ui.one("unknown")
    ui=NativeUI(Mock(),{"message":{"value":"unique","evidence":"actual.xml"}},timeout=.01)
    first,second=Mock(),Mock(); first.is_displayed.return_value=True;second.is_displayed.return_value=True
    ui.driver.find_elements.return_value=[first,second]
    with pytest.raises(AssertionError,match="Ambiguous"):ui.one("message")


def test_configuration_never_accepts_empty_postman_account_export(tmp_path):
    env=tmp_path/"postman.json";env.write_text(json.dumps({"values":[{"key":"phone_a","value":"","enabled":True}]}))
    config=tmp_path/"execution.json";config.write_text(json.dumps({
        "api_origin":"https://dev-api.velowind.com","observed_app_origin":"https://dev-api.velowind.com",
        "environment_evidence":"observed request","postman_environment":str(env)}))
    with pytest.raises(Blocked,match="Missing Postman/environment"):read_configuration(config)


def test_grouped_accounts_load_username_password_and_id_together(tmp_path, monkeypatch):
    for role in ("a","b","c"):
        for field in ("phone","password","user_id","name"): monkeypatch.delenv(field+"_"+role,raising=False)
    accounts={role:{"username":"test-phone-"+role,"password":"fake-secret-"+role,
                    "user_id":"id-"+role,"name":"name-"+role} for role in ("a","b","c")}
    (tmp_path/"accounts.json").write_text(json.dumps({"accounts":accounts}))
    config=tmp_path/"execution.json";config.write_text(json.dumps({
        "api_origin":"https://dev-api.velowind.com","observed_app_origin":"https://dev-api.velowind.com",
        "environment_evidence":"observed request","accounts_file":"accounts.json"}))
    _,loaded=read_configuration(config)
    assert loaded["a"]=={"phone":"test-phone-a","password":"fake-secret-a","user_id":"id-a","name":"name-a"}
    monkeypatch.setenv("password_a","overridden-fake-secret")
    assert read_configuration(config)[1]["a"]["password"]=="overridden-fake-secret"
    assert json.loads((tmp_path/"accounts.json").read_text())["accounts"]["a"]["password"]=="fake-secret-a"


def test_malformed_grouped_accounts_are_rejected_without_exposing_content(tmp_path):
    (tmp_path/"accounts.json").write_text(json.dumps({"accounts":{"a":"private-value"}}))
    config=tmp_path/"execution.json";config.write_text(json.dumps({
        "api_origin":"https://dev-api.velowind.com","observed_app_origin":"https://dev-api.velowind.com",
        "environment_evidence":"observed request","accounts_file":"accounts.json"}))
    with pytest.raises(Blocked) as error:read_configuration(config)
    assert "private-value" not in str(error.value)


def test_binding_executes_actual_api_query_and_checks_returned_fact():
    api=Mock();api.request.return_value={"unreadCount":3}
    binding={"read":{"source":"collection-request","steps":[
        {"kind":"api","actor":"a","method":"GET","path":"/api/v1/mobile/example","save":"result"},
        {"kind":"assert","actual":"${result.unreadCount}","expected":3}],
        "output":{"count":"${result.unreadCount}"}}}
    program=Program(api,{"a":A},{},binding,{},[])
    assert program.run("read")=={"count":3}
    api.request.return_value={"unreadCount":2}
    with pytest.raises(AssertionError):program.run("read")


def test_history_older_uses_oldest_anchor_and_finds_all_pages():
    api=Mock()
    api.request.side_effect=[
        {'messages':[{'messageId':'3'},{'messageId':'4'}], 'hasMore':True,'oldestReturnedMessageId':'3'},
        {'messages':[{'messageId':'1'},{'messageId':'2'}], 'hasMore':False}]
    result=Messages(api).history(A,'peer',direction='older',page_size=2,expected_ids=['1','4'])
    assert set(result)=={'1','2','3','4'}
    assert api.request.call_args.kwargs['params']=={'pageSize':2,'beforeMessageId':'3'}


def test_notification_pagination_keeps_snapshot_for_next_page():
    api=API('https://dev-api.velowind.com')
    api.request=Mock(side_effect=[{'items':[{'id':'1'}],'total':2,'querySnapshot':'snap'},
                                  {'items':[{'id':'2'}],'total':2,'querySnapshot':'snap'}])
    assert len(api.pages(A,'/api/v1/mobile/items',id_key='id'))==2
    assert api.request.call_args.kwargs['params']['querySnapshot']=='snap'


def test_http_business_failure_keeps_safe_code_without_response_secrets():
    from urllib.error import HTTPError
    from velowind_appium.message_regression.core import ApiFailure
    opener=Mock()
    opener.open.side_effect=HTTPError('https://dev-api.velowind.com',400,'private-value',{},
        io.BytesIO(b'{"code":17000075,"messageKey":"message.chatroom.owner_required","message":"private-token"}'))
    api=API('https://dev-api.velowind.com',opener=opener)
    with pytest.raises(ApiFailure) as caught:api.request(A,'PUT','/api/v1/mobile/group',body={'name':'test'})
    assert caught.value.code==17000075
    assert caught.value.message_key=='message.chatroom.owner_required'
    assert 'private' not in str(caught.value)+json.dumps(api.journal)


def test_group_member_search_uses_search_route_and_member_id():
    api=Mock();api.pages.return_value=[]
    Messages(api).members(A,'group',keyword='Name')
    assert api.pages.call_args.args[1].endswith('/group/members/search')
    assert api.pages.call_args.kwargs['id_key']=='memberUserId'


def test_group_detail_requires_nested_actual_chatroom_contract():
    api=Mock();api.request.return_value={'chatroom':{'chatroomId':'group','memberCount':1}}
    assert Messages(api).group(A,'group')['memberCount']==1
    api.request.return_value={'chatroom':{'chatroomId':'another'}}
    with pytest.raises(AssertionError,match='ID mismatch'):Messages(api).group(A,'group')


def test_live_unknown_create_is_reconciled_and_dissolved_without_retry(tmp_path):
    from velowind_appium.message_regression.live import LiveRun
    from velowind_appium.message_regression.core import ApiFailure
    run=LiveRun.__new__(LiveRun)
    run.output=tmp_path;run.run_id='12345678';run.actors={r:A for r in 'abc'}
    run.api=Mock();run.api.journal=[]
    run.api.request.return_value={'items':[{'chatroomId':'created','chatroomName':'消息12345678'}]}
    run.report={'cases':[],'resources':[]};run.messages=Mock()
    run.messages.create_group.side_effect=ApiFailure()
    run.messages.group.side_effect=[{'chatroomStatus':'ACTIVE'},{'chatroomStatus':'DISSOLVED_READ_ONLY'}]
    with pytest.raises(ApiFailure):run.groups()
    run.messages.create_group.assert_called_once()
    assert run.report['cases'][0]['status']=='failed'
    assert run.report['resources'][0]['status']=='dissolved-read-only'
    assert any(c.args[1]=='POST' and c.args[2].endswith('/dissolve') for c in run.api.request.call_args_list)


def test_native_receipt_is_bound_to_current_message_and_latest_is_unobscured():
    from xml.etree import ElementTree as E
    from velowind_appium.message_regression.ios_live import OwnedIOS
    root=E.fromstring('''<root><row><text type="XCUIElementTypeStaticText" name="old"/><text type="XCUIElementTypeStaticText" name="已读"/></row>
    <row><text type="XCUIElementTypeStaticText" name="new" visible="true" y="600" height="30"/><text type="XCUIElementTypeStaticText" name="已发送"/></row>
    <text type="XCUIElementTypeStaticText" name="输入消息..." visible="true" y="700"/></root>''')
    assert OwnedIOS.receipt(root,'new')=='已发送'
    assert OwnedIOS.receipt(root,'old')=='已读'
    ui=OwnedIOS.__new__(OwnedIOS);ui.assert_latest(root,'new')
    next(e for e in root.iter() if e.get('name')=='new').set('y','690')
    with pytest.raises(AssertionError,match='obscured'):ui.assert_latest(root,'new')


def test_media_fixture_decodes_and_signed_host_guard_rejects_untrusted_targets():
    from PIL import Image
    from velowind_appium.message_regression.media import fixture_png,trusted_url
    png=fixture_png('current-run')
    picture=Image.open(io.BytesIO(png));picture.load()
    assert picture.size==(64,64)
    assert fixture_png('other-run')!=png
    for url in ['http://bucket.aliyuncs.com','https://evil.com/image','https://bucket.aliyuncs.com.evil/image','https://x@y.velowind.com/image']:
        with pytest.raises(AssertionError):trusted_url(url)


def test_image_acknowledgement_does_not_count_as_delivery():
    api=Mock()
    actual={'messageId':'persisted','senderUserId':A.user_id,'content':None,'clientMessageId':'req-image'}
    api.request.side_effect=[{'messageId':'temporary','content':'处理中'},
        {'status':'SENT','contentAvailable':True,'message':actual}]
    result=Messages(api).send(A,'group','',group=True,image_ids=['asset'],client_id='req-image')
    assert result['messageId']=='persisted'
    assert sum(c.args[1]=='POST' for c in api.request.call_args_list)==1
    assert api.request.call_args.args[2].endswith('/message-send-results/req-image')


def test_failed_or_unknown_image_send_is_never_resent():
    for state,exception in [('FAILED',AssertionError),('UNKNOWN',Blocked)]:
        api=Mock();api.request.side_effect=[{'messageId':'temporary'},{'status':state}]
        with pytest.raises(exception):Messages(api).send(A,'group','',group=True,image_ids=['asset'],client_id='req-image')
        assert sum(c.args[1]=='POST' for c in api.request.call_args_list)==1


def test_admin_login_checks_same_account_and_fresh_session_without_password_changes():
    api=API('https://dev-api.velowind.com')
    api.request=Mock(side_effect=[{'userId':A.user_id,'accessToken':'private-token','passwordResetRequired':False},
                                 {'userId':A.user_id,'roles':['ADMIN'],'passwordResetRequired':False}])
    assert api.login_admin('username','password',expected_id=A.user_id,name='A').user_id==A.user_id
    assert [c.args[1] for c in api.request.call_args_list]==['POST','GET']
