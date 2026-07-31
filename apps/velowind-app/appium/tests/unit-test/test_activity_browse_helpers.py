from velowind_appium.modules import activity_browse


def test_activity_feed_contains_category_results_requires_activity_card_content():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="全部活动" />
      <XCUIElementTypeStaticText name="骑行" />
      <XCUIElementTypeOther name="环莫干山一日骑行活动 浙江省·湖州市 a admin 骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
      <XCUIElementTypeOther name="骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
    </AppiumAUT>
    """

    assert activity_browse.activity_feed_contains_category_results(page_source, "骑行") is True
    assert activity_browse.activity_feed_category_result_texts(page_source, "骑行") == [
        "骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级"
    ]


def test_activity_feed_extracts_android_card_with_separate_text_nodes():
    page_source = """
    <hierarchy>
      <android.view.ViewGroup>
        <android.widget.TextView text="骑行" displayed="true" />
        <android.view.ViewGroup>
          <android.widget.TextView text="总里程" displayed="true" />
          <android.widget.TextView text="时长" displayed="true" />
          <android.widget.TextView text="场次" displayed="true" />
          <android.widget.TextView text="难度等级" displayed="true" />
          <android.widget.TextView text="34" displayed="true" />
          <android.widget.TextView text="1天" displayed="true" />
          <android.widget.TextView text="0场" displayed="true" />
        </android.view.ViewGroup>
      </android.view.ViewGroup>
    </hierarchy>
    """

    assert activity_browse.activity_feed_category_result_texts(page_source, "骑行") == [
        "骑行 总里程 时长 场次 难度等级 34 1天 0场"
    ]


def test_activity_search_extracts_android_result_title_from_parent_card():
    page_source = """
    <hierarchy>
      <android.widget.ScrollView displayed="true">
        <android.view.ViewGroup bounds="[42,363][1238,1282]" displayed="true">
          <android.widget.TextView text="张家界大环线2天1晚" displayed="true" bounds="[42,405][1013,483]" />
          <android.widget.TextView text="浙江省·张家界市" displayed="true" bounds="[99,501][392,549]" />
          <android.widget.TextView text="Nancy" displayed="true" bounds="[1115,501][1238,546]" />
          <android.view.ViewGroup bounds="[42,567][1238,1240]" displayed="true">
            <android.widget.TextView text="骑行" displayed="true" />
            <android.widget.TextView text="总里程" displayed="true" />
            <android.widget.TextView text="时长" displayed="true" />
            <android.widget.TextView text="场次" displayed="true" />
            <android.widget.TextView text="难度等级" displayed="true" />
            <android.widget.TextView text="128" displayed="true" />
            <android.widget.TextView text="2天1晚" displayed="true" />
            <android.widget.TextView text="2场" displayed="true" />
          </android.view.ViewGroup>
        </android.view.ViewGroup>
      </android.widget.ScrollView>
    </hierarchy>
    """

    assert activity_browse.activity_text_search_result_texts(page_source, "张家界") == [
        "张家界大环线2天1晚 浙江省·张家界市 Nancy 骑行 总里程 时长 场次 难度等级 128 2天1晚 2场"
    ]


def test_activity_feed_uses_category_tag_row_to_match_results():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="环莫干山一日活动 浙江省·湖州市 a admin 徒步 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
      <XCUIElementTypeOther name="徒步 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
    </AppiumAUT>
    """

    all_results_match, mismatched = activity_browse.activity_feed_all_results_match_category(page_source, "骑行")

    assert all_results_match is False
    assert mismatched == ["徒步 总里程 -- 时长 约8.5小时 场次 0场 难度等级"]


def test_activity_feed_contains_category_results_rejects_navigation_only():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="全部活动" />
      <XCUIElementTypeStaticText name="骑行" />
      <XCUIElementTypeStaticText name="徒步" />
    </AppiumAUT>
    """

    assert activity_browse.activity_feed_contains_category_results(page_source, "骑行") is False


def test_activity_feed_all_results_match_category_rejects_mixed_activity_cards():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="环莫干山一日骑行活动 浙江省·湖州市 a admin 骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
      <XCUIElementTypeOther name="希夏邦马大环线徒步线路 西藏自治区·日喀则市 a admin 徒步 总里程 2800 时长 11天 场次 0场 难度等级" />
    </AppiumAUT>
    """

    all_results_match, mismatched = activity_browse.activity_feed_all_results_match_category(page_source, "骑行")

    assert all_results_match is False
    assert mismatched == [
        "希夏邦马大环线徒步线路 西藏自治区·日喀则市 a admin 徒步 总里程 2800 时长 11天 场次 0场 难度等级"
    ]


def test_activity_feed_all_results_match_category_ignores_container_rows():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="全部活动 骑行 徒步 环莫干山一日骑行活动 浙江省·湖州市 a admin 骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级 希夏邦马大环线徒步线路 西藏自治区·日喀则市 a admin 徒步 总里程 2800 时长 11天 场次 0场 难度等级" />
      <XCUIElementTypeOther name="环莫干山一日骑行活动 浙江省·湖州市 a admin 骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
    </AppiumAUT>
    """

    assert activity_browse.activity_feed_all_results_match_category(page_source, "骑行") == (True, [])


def test_activity_feed_all_results_match_category_ignores_metric_only_rows():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="环莫干山一日骑行活动 浙江省·湖州市 a admin 骑行 总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
      <XCUIElementTypeOther name="总里程 -- 时长 约8.5小时 场次 0场 难度等级" />
    </AppiumAUT>
    """

    assert activity_browse.activity_feed_all_results_match_category(page_source, "骑行") == (True, [])


def test_activity_text_search_result_texts_returns_visible_keyword_cards_only():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="全部活动 骑行 徒步 张家界大环线2天1晚 浙江省·张家界市 Nancy 骑行 总里程 128 时长 2天1晚 场次 2场 难度等级" visible="false" />
      <XCUIElementTypeOther name="张家界大环线 2 天 1 晚 湖南省·张家界市 寻风者 骑行 总里程 64 时长 2天1晚 场次 0场 难度等级" visible="true" />
      <XCUIElementTypeOther name="长张300穿越骑 2 天 1 晚 湖南省·长沙市 白泽泽 骑行 总里程 300 时长 2天1晚 场次 0场 难度等级" visible="true" />
    </AppiumAUT>
    """

    assert activity_browse.activity_text_search_result_texts(page_source, "张家界") == [
        "张家界大环线 2 天 1 晚 湖南省·张家界市 寻风者 骑行 总里程 64 时长 2天1晚 场次 0场 难度等级"
    ]


def test_parse_activity_detail_snapshot_extracts_visible_route_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="activity-route-detail-v3-hero-carousel" visible="true" />
      <XCUIElementTypeImage visible="true" />
      <XCUIElementTypeStaticText name="张家界大环线2天1晚" label="张家界大环线2天1晚" value="张家界大环线2天1晚" visible="true" x="13" y="235" width="180" height="26" />
      <XCUIElementTypeStaticText name="浙江省·张家界市" label="浙江省·张家界市" value="浙江省·张家界市" visible="true" x="28" y="270" width="98" height="18" />
      <XCUIElementTypeOther name="总里程 128 公里 参考时长 2 天1 晚 风险等级" visible="true" />
      <XCUIElementTypeOther name="风景标签 峰林 峡谷 山地公路 沿途景点 武陵源 天门山 张家界国家森林公园" visible="true" />
      <XCUIElementTypeOther name="Nancy 路线主理人" visible="true" />
      <XCUIElementTypeOther name="ROUTE 路线说明 活动概览 参考张家界大环线2天1晚活动设计，串联武陵源、天门山周边山地景观道路，适合具备稳定爬坡和长距离骑行经验的用户参与。" visible="true" />
      <XCUIElementTypeOther name="COMMENTS 活动评论 查看更多 前往评论页查看真实活动评论" visible="true" />
      <XCUIElementTypeOther name="请选择场次 1/2 场次信息 集合地点 张家界国家森林公园" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_activity_detail_snapshot(page_source)

    assert snapshot.title == "张家界大环线2天1晚"
    assert snapshot.location == "浙江省·张家界市"
    assert snapshot.publisher == "Nancy"
    assert snapshot.is_basic_detail_complete()


def test_tap_first_activity_card_tries_next_point_until_detail_opens(monkeypatch):
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="张家界大环线2天1晚 浙江省·张家界市 Nancy 骑行 总里程 128 时长 2天1晚 场次 2场 难度等级" visible="true" x="13" y="119" width="376" height="283" />
    </AppiumAUT>
    """
    taps = []

    class FakeDriver:
        def execute_script(self, script, payload):
            taps.append((payload["x"], payload["y"]))

    def verify_open():
        return len(taps) >= 2

    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    assert activity_browse._tap_first_activity_card(FakeDriver(), page_source, verify_open=verify_open) is True
    assert len(taps) == 2


def test_parse_activity_signup_snapshot_extracts_registration_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="活动报名" visible="true" />
      <XCUIElementTypeOther name="8月04日 周二 - 8月04日 周二 09:25 - 18:25 集合地点 张家界国家森林公园 报名截止 8月03日 周一 18:20 活动名额 剩余 20 / 20 服务配置 领骑 补给车 保险" visible="true" />
      <XCUIElementTypeOther name="报名信息 姓名 请输入报名人姓名 证件类型 请选择证件类型 证件号码 请输入证件号码 通知手机号 请输入通知手机号" visible="true" />
      <XCUIElementTypeOther name="报名规则 取消规则 无罚金 报名说明 请确认报名信息真实有效，提交后将按活动规则处理；如涉及支付或审核，请留意后续状态变化。" visible="true" />
      <XCUIElementTypeOther name="报名费用 ¥0.01 / 人 提交订单" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.title_visible
    assert snapshot.meeting_location == "张家界国家森林公园"
    assert snapshot.registration_fields_visible
    assert snapshot.rules_visible
    assert snapshot.fee_visible
    assert snapshot.submit_order_visible
    assert snapshot.is_basic_signup_complete()


def test_parse_activity_signup_snapshot_extracts_entered_identity_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="活动报名 报名信息 姓名 自动化报名测试 证件类型 身份证 证件号码 110101199001011237 通知手机号 13800138000 报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单" visible="true" />
    </AppiumAUT>
    """
    draft = activity_browse.build_activity_signup_draft()

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.name == draft.name
    assert snapshot.certificate_type == draft.certificate_type
    assert snapshot.certificate_number == draft.certificate_number
    assert snapshot.phone == draft.phone
    assert snapshot.matches_draft(draft)


def test_parse_activity_signup_snapshot_prefers_text_field_values_over_container_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="报名信息 姓名 证件类型 身份证 证件号码 通知手机号" visible="true" />
      <XCUIElementTypeTextField value="自动化报名测试" visible="true" placeholderValue="请输入报名人姓名" />
      <XCUIElementTypeStaticText name="身份证" label="身份证" value="身份证" visible="true" />
      <XCUIElementTypeTextField value="110101199001011237" visible="true" placeholderValue="请输入证件号码" />
      <XCUIElementTypeTextField value="13800138000" visible="true" placeholderValue="请输入通知手机号" />
      <XCUIElementTypeOther name="报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单" visible="true" />
    </AppiumAUT>
    """
    draft = activity_browse.build_activity_signup_draft()

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.matches_draft(draft)


def test_activity_signup_consent_prompt_is_detected():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="报名提示 我确认报名人满足参与活动的最低年龄要求，并已阅读并同意《活动条款》 稍后再说 同意并继续" visible="true" />
    </AppiumAUT>
    """

    assert activity_browse._activity_signup_consent_prompt_visible(page_source)


def test_fill_activity_signup_form_enters_draft_and_waits_for_echo(monkeypatch):
    draft = activity_browse.build_activity_signup_draft()
    calls = []

    class FakeDriver:
        @property
        def page_source(self):
            if len(calls) >= 4:
                return (
                    "活动报名 报名信息 "
                    f"姓名 {draft.name} 证件类型 {draft.certificate_type} "
                    f"证件号码 {draft.certificate_number} 通知手机号 {draft.phone} "
                    "报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单"
                )
            return "活动报名 报名信息 姓名 请输入报名人姓名 证件类型 请选择证件类型 证件号码 请输入证件号码 通知手机号 请输入通知手机号 提交订单"

    def fill_field(driver, placeholder, value):
        calls.append(("field", placeholder, value))
        return True

    def select_type(driver, certificate_type):
        calls.append(("type", certificate_type))
        return True

    monkeypatch.setattr(activity_browse, "_fill_signup_text_field_by_placeholder", fill_field, raising=False)
    monkeypatch.setattr(activity_browse, "_select_signup_certificate_type", select_type, raising=False)
    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    snapshot = activity_browse.fill_activity_signup_form(FakeDriver(), draft, timeout=3)

    assert snapshot.matches_draft(draft)
    assert calls == [
        ("field", "请输入报名人姓名", draft.name),
        ("type", draft.certificate_type),
        ("field", "请输入证件号码", draft.certificate_number),
        ("field", "请输入通知手机号", draft.phone),
    ]
