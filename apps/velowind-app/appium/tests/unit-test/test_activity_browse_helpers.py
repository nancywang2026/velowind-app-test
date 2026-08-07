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


def test_wait_for_activity_category_results_reloads_network_error(monkeypatch):
    events = []
    page = {"source": "全部活动 骑行 加载失败 网络连接异常 重新加载"}
    clock = {"value": 0.0}

    class FakeDriver:
        pass

    def fake_tap_text(driver, text, timeout=1):
        events.append(("tap-text", text))
        page["source"] = "骑行 总里程 -- 时长 约8.5小时 场次 1场 难度等级"
        return True

    def fake_monotonic():
        clock["value"] += 0.1
        return clock["value"]

    monkeypatch.setattr(activity_browse, "_safe_page_source", lambda driver: page["source"])
    monkeypatch.setattr(activity_browse, "tap_text_if_present", fake_tap_text)
    monkeypatch.setattr(activity_browse.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    assert activity_browse.wait_for_activity_category_results(FakeDriver(), "骑行", timeout=2)
    assert events == [("tap-text", "重新加载")]


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


def test_activity_search_accepts_android_split_title_and_location_results():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="全部活动" displayed="true" />
      <android.widget.TextView text="张家界大环线2天1晚" displayed="true" bounds="[45,249][846,315]" />
      <android.widget.TextView text="浙江省·张家界市" displayed="true" bounds="[90,328][330,368]" />
      <android.widget.TextView text="Nancy" displayed="true" />
    </hierarchy>
    """

    assert activity_browse.activity_text_search_result_texts(page_source, "张家界") == [
        "张家界大环线2天1晚",
        "浙江省·张家界市",
    ]


def test_activity_card_tap_points_include_android_split_card_container_bounds():
    page_source = """
    <hierarchy>
      <android.widget.ScrollView displayed="true">
        <android.view.ViewGroup displayed="true" bounds="[42,633][1238,1282]">
          <android.widget.TextView text="南北驼梁徒步穿越" displayed="true" bounds="[45,633][846,699]" />
          <android.widget.TextView text="河北省·石家庄市" displayed="true" />
          <android.widget.TextView text="徒步" displayed="true" />
          <android.widget.TextView text="总里程" displayed="true" />
          <android.widget.TextView text="时长" displayed="true" />
          <android.widget.TextView text="场次" displayed="true" />
          <android.widget.TextView text="难度等级" displayed="true" />
          <android.widget.TextView text="20" displayed="true" />
          <android.widget.TextView text="2天" displayed="true" />
          <android.widget.TextView text="0场" displayed="true" />
        </android.view.ViewGroup>
      </android.widget.ScrollView>
    </hierarchy>
    """

    assert activity_browse._activity_card_tap_points(page_source) == [(640, 849), (640, 957)]


def test_activity_card_tap_points_include_android_metric_container_when_title_is_sibling():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="南北驼梁徒步穿越" displayed="true" bounds="[45,633][846,699]" />
      <android.view.ViewGroup displayed="true" bounds="[45,765][1035,1322]">
        <android.widget.TextView text="徒步" displayed="true" />
        <android.widget.TextView text="总里程" displayed="true" />
        <android.widget.TextView text="时长" displayed="true" />
        <android.widget.TextView text="场次" displayed="true" />
        <android.widget.TextView text="难度等级" displayed="true" />
        <android.widget.TextView text="126" displayed="true" />
        <android.widget.TextView text="7天" displayed="true" />
        <android.widget.TextView text="0场" displayed="true" />
      </android.view.ViewGroup>
    </hierarchy>
    """

    assert activity_browse._activity_card_tap_points(page_source) == [(540, 950), (540, 1043)]


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


def test_open_activity_search_coordinate_fallback_targets_android_header_icon(monkeypatch):
    events = []
    page_sources = iter(["activity-feed", "activity-feed", "activity-search"])

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_rect(self):
            return {"width": 1080, "height": 2400}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity_browse, "_activity_search_visible", lambda source: source == "activity-search")
    monkeypatch.setattr(activity_browse, "_safe_page_source", lambda driver: next(page_sources, "activity-search"))

    activity_browse.open_activity_search(FakeDriver(), timeout=0.1)

    assert events == [("mobile: tap", {"x": 1000, "y": 141})]


def test_open_activity_search_coordinate_uses_android_search_icon_bounds(monkeypatch):
    events = []
    page_source = """
    <hierarchy width="1280" height="2568">
      <android.widget.HorizontalScrollView bounds="[265,196][1098,290]" displayed="true" />
      <android.view.ViewGroup bounds="[1127,196][1238,290]" displayed="true">
        <com.horcrux.svg.SvgView bounds="[1153,214][1212,272]" displayed="true" />
      </android.view.ViewGroup>
    </hierarchy>
    """
    page_sources = iter([page_source, "activity-search"])

    class FakeDriver:
        capabilities = {"platformName": "Android"}

        def get_window_rect(self):
            return {"width": 1080, "height": 2400}

        def execute_script(self, script, payload):
            events.append((script, payload))

    monkeypatch.setattr(activity_browse, "_activity_search_visible", lambda source: source == "activity-search")
    monkeypatch.setattr(activity_browse, "_safe_page_source", lambda driver: next(page_sources, "activity-search"))

    activity_browse.open_activity_search(FakeDriver(), timeout=0.1)

    assert events == [("mobile: tap", {"x": 1182, "y": 243})]


def test_tap_activity_search_submit_falls_back_to_keyboard_search(monkeypatch):
    events = []

    class FakeDriver:
        def execute_script(self, script, payload):
            events.append((script, payload))
            return False

        def hide_keyboard(self, **kwargs):
            events.append(("hide_keyboard", kwargs))

    monkeypatch.setattr(activity_browse, "tap_text_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(activity_browse, "tap_by_coordinate_ratios", lambda *args, **kwargs: False)

    assert activity_browse._tap_activity_search_submit(FakeDriver()) is True
    assert ("hide_keyboard", {"key_name": "Search"}) in events


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


def test_parse_activity_detail_snapshot_accepts_route_heading_without_overview():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="activity-route-detail-v3-hero-carousel" visible="true" />
      <XCUIElementTypeImage visible="true" />
      <XCUIElementTypeStaticText name="上海出发到杭州" visible="true" x="13" y="235" width="180" height="26" />
      <XCUIElementTypeStaticText name="浙江省·杭州" visible="true" x="28" y="270" width="98" height="18" />
      <XCUIElementTypeOther name="总里程 -- 参考时长 -- 风险等级" visible="true" />
      <XCUIElementTypeOther name="风景标签 沿途景点" visible="true" />
      <XCUIElementTypeOther name="Nancy 路线主理人" visible="true" />
      <XCUIElementTypeOther name="ROUTE 路线说明 上海 浦东" visible="true" />
      <XCUIElementTypeOther name="COMMENTS 活动评论 查看更多" visible="true" />
      <XCUIElementTypeOther name="请选择场次 1/1 场次信息 集合地点 陆家嘴" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_activity_detail_snapshot(page_source)

    assert snapshot.route_visible
    assert snapshot.is_basic_detail_complete()


def test_parse_activity_detail_snapshot_accepts_android_route_itinerary_without_overview_heading():
    page_source = """
    <hierarchy>
      <android.widget.FrameLayout resource-id="activity-route-detail-v3-hero-carousel" displayed="true" />
      <android.widget.ImageView resource-id="image" displayed="true" />
      <android.widget.TextView text="一起去徒步吧" displayed="true" bounds="[0,249][522,315]" />
      <android.widget.TextView text="青海省·黄南藏族" displayed="true" />
      <android.widget.TextView text="Nancy" displayed="true" />
      <android.widget.TextView text="路线主理人" displayed="true" />
      <android.widget.TextView text="总里程" displayed="true" />
      <android.widget.TextView text="参考时长" displayed="true" />
      <android.widget.TextView text="风险等级" displayed="true" />
      <android.widget.TextView text="风景标签" displayed="true" />
      <android.widget.TextView text="沿途景点" displayed="true" />
      <android.widget.TextView text="Day1" displayed="true" />
      <android.widget.TextView text="路线说明待补充" displayed="true" />
      <android.widget.TextView text="活动评论" displayed="true" />
      <android.widget.TextView text="集合地点" displayed="true" />
    </hierarchy>
    """

    snapshot = activity_browse.parse_activity_detail_snapshot(page_source)

    assert snapshot.route_visible is True
    assert snapshot.is_basic_detail_complete()


def test_parse_activity_detail_snapshot_accepts_android_route_tab_and_empty_sessions():
    page_source = """
    <hierarchy>
      <android.widget.FrameLayout resource-id="activity-route-detail-v3-hero-carousel" displayed="true" />
      <android.widget.ImageView resource-id="image" displayed="true" />
      <android.widget.TextView text="荆门市区 + 漳河水库 2 天 1 晚骑行活动" displayed="true" bounds="[0,249][522,315]" />
      <android.widget.TextView text="湖北省·荆门市" displayed="true" />
      <android.widget.TextView text="瓜瓜" displayed="true" />
      <android.widget.TextView text="路线主理人" displayed="true" />
      <android.widget.TextView text="总里程" displayed="true" />
      <android.widget.TextView text="参考时长" displayed="true" />
      <android.widget.TextView text="风险等级" displayed="true" />
      <android.widget.TextView text="风景标签" displayed="true" />
      <android.widget.TextView text="沿途景点" displayed="true" />
      <android.widget.TextView text="路线说明" displayed="true" />
      <android.widget.TextView text="活动评论" displayed="true" />
      <android.widget.TextView text="暂无场次" displayed="true" />
    </hierarchy>
    """

    snapshot = activity_browse.parse_activity_detail_snapshot(page_source)

    assert snapshot.route_visible is True
    assert snapshot.sessions_visible is True
    assert snapshot.is_basic_detail_complete()


def test_activity_detail_visible_while_android_content_is_loading():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="活动详情" />
      <android.widget.ProgressBar text="0.0" />
      <android.widget.FrameLayout resource-id="activity-discovery-v2-filter-pager" />
    </hierarchy>
    """

    assert activity_browse.activity_detail_is_visible(page_source) is True


def test_read_activity_detail_waits_past_android_loading_shell(monkeypatch):
    states = [
        """
        <hierarchy>
          <android.widget.TextView text="活动详情" />
          <android.widget.ProgressBar text="0.0" />
        </hierarchy>
        """,
        """
        <hierarchy>
          <android.widget.FrameLayout resource-id="activity-route-detail-v3-hero-carousel" />
          <android.widget.ImageView resource-id="image" />
          <android.widget.TextView text="张家界大环线2天1晚" bounds="[0,220][500,280]" />
          <android.widget.TextView text="浙江省·张家界市" />
          <android.widget.TextView text="Nancy" />
          <android.widget.TextView text="路线主理人" />
          <android.widget.TextView text="总里程" />
          <android.widget.TextView text="参考时长" />
          <android.widget.TextView text="风险等级" />
          <android.widget.TextView text="风景标签" />
          <android.widget.TextView text="沿途景点" />
          <android.widget.TextView text="路线说明" />
          <android.widget.TextView text="活动概览" />
          <android.widget.TextView text="活动评论" />
          <android.widget.TextView text="请选择场次" />
        </hierarchy>
        """,
    ]

    class FakeDriver:
        @property
        def page_source(self):
            return states.pop(0) if len(states) > 1 else states[0]

    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    snapshot = activity_browse.read_activity_detail_snapshot(FakeDriver(), timeout=3)

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


def test_open_first_signup_available_activity_detail_skips_ended_activity(monkeypatch):
    feed_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="已结束活动 浙江省·张家界市 Nancy 骑行 总里程 128 时长 2天1晚 场次 2场 难度等级" visible="true" x="13" y="119" width="376" height="283" />
      <XCUIElementTypeOther name="可报名活动 浙江省·湖州市 a admin 骑行 总里程 64 时长 1天 场次 1场 难度等级" visible="true" x="13" y="430" width="376" height="283" />
    </AppiumAUT>
    """
    state = {"source": feed_source}
    taps = []

    class FakeDriver:
        @property
        def page_source(self):
            return state["source"]

        def execute_script(self, script, payload):
            taps.append((payload["x"], payload["y"]))
            if payload["y"] < 430:
                state["source"] = "activity-route-detail-v3-hero-carousel 活动详情 报名结束"
            else:
                state["source"] = "activity-route-detail-v3-hero-carousel 活动详情 确认报名"

        def back(self):
            state["source"] = feed_source

    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    activity_browse.open_first_signup_available_activity_detail(FakeDriver(), timeout=3)

    assert state["source"] == "activity-route-detail-v3-hero-carousel 活动详情 确认报名"
    assert taps[0][1] < 430
    assert taps[-1][1] >= 430


def test_return_to_activity_feed_taps_ios_header_back_when_native_back_keeps_detail_open(monkeypatch):
    events = []

    class FakeDriver:
        capabilities = {"platformName": "iOS"}

        def back(self):
            events.append("back")

    wait_results = iter([False, True])
    monkeypatch.setattr(activity_browse, "_wait_until", lambda condition, timeout: next(wait_results))
    monkeypatch.setattr(
        activity_browse,
        "tap_by_coordinate_ratios",
        lambda driver, ratios: events.append(("tap", ratios)) or True,
    )

    activity_browse._return_to_activity_feed(FakeDriver())

    assert events == [
        "back",
        ("tap", [(0.07, 0.10), (0.08, 0.11)]),
    ]


def test_activity_signup_unavailable_detects_ended_action():
    assert activity_browse.activity_signup_unavailable("activity-route-detail-v3-hero-carousel 报名结束") is True
    assert activity_browse.activity_signup_unavailable("activity-route-detail-v3-hero-carousel 确认报名") is False


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


def test_parse_activity_signup_snapshot_accepts_self_registration_summary():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="活动报名" visible="true" />
      <XCUIElementTypeOther name="8月05日 周三 - 8月05日 周三 09:50 - 18:50 集合地点 张家界国家森林公园 报名截止 8月04日 周二 18:45 活动名额 剩余 19 / 20 服务配置 领骑 补给车 保险" visible="true" />
      <XCUIElementTypeOther name="报名信息 本人" visible="true" />
      <XCUIElementTypeOther name="报名规则 取消规则 无罚金 报名说明 请确认报名信息真实有效，提交后将按活动规则处理；如涉及支付或审核，请留意后续状态变化。" visible="true" />
      <XCUIElementTypeOther name="报名费用 ¥0.01 / 人 提交订单" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.registration_fields_visible
    assert snapshot.self_registration_selected
    assert snapshot.is_basic_signup_complete()


def test_parse_activity_signup_snapshot_extracts_entered_identity_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeOther name="活动报名 报名信息 姓名 自动化报名测试 证件类型 身份证 证件号码 110000199001010013 通知手机号 13800138000 报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单" visible="true" />
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
      <XCUIElementTypeTextField value="110000199001010013" visible="true" placeholderValue="请输入证件号码" />
      <XCUIElementTypeTextField value="13800138000" visible="true" placeholderValue="请输入通知手机号" />
      <XCUIElementTypeOther name="报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单" visible="true" />
    </AppiumAUT>
    """
    draft = activity_browse.build_activity_signup_draft()

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.matches_draft(draft)


def test_parse_activity_signup_snapshot_reads_android_edit_text_values_by_hint():
    page_source = """
    <hierarchy>
      <android.widget.TextView text="活动报名" displayed="true" />
      <android.widget.TextView text="报名信息" displayed="true" />
      <android.widget.TextView text="姓名" displayed="true" />
      <android.widget.EditText text="自动化报名测试" hint="请输入报名人姓名" displayed="true" />
      <android.widget.TextView text="证件类型" displayed="true" />
      <android.widget.TextView text="身份证" displayed="true" />
      <android.widget.TextView text="证件号码" displayed="true" />
      <android.widget.EditText text="110000199001010013" hint="请输入证件号码" displayed="true" />
      <android.widget.TextView text="通知手机号" displayed="true" />
      <android.widget.EditText text="13800138000" hint="请输入通知手机号" displayed="true" />
      <android.widget.TextView text="报名规则" displayed="true" />
      <android.widget.TextView text="取消规则" displayed="true" />
      <android.widget.TextView text="报名说明" displayed="true" />
      <android.widget.TextView text="报名费用" displayed="true" />
      <android.widget.TextView text="¥0.01 / 人" displayed="true" />
      <android.widget.TextView text="提交订单" displayed="true" />
    </hierarchy>
    """
    draft = activity_browse.build_activity_signup_draft()

    snapshot = activity_browse.parse_activity_signup_snapshot(page_source)

    assert snapshot.matches_draft(draft)


def test_fill_signup_text_field_by_placeholder_supports_android_hint(monkeypatch):
    calls = []

    class FakeElement:
        pass

    class FakeDriver:
        def find_element(self, by, xpath):
            calls.append((by, xpath))
            if "android.widget.EditText" in xpath and '@hint="请输入报名人姓名"' in xpath:
                return FakeElement()
            raise activity_browse.NoSuchElementException("missing")

    filled = []
    monkeypatch.setattr(activity_browse, "_replace_text", lambda element, value: filled.append(value))
    monkeypatch.setattr(activity_browse, "_hide_keyboard", lambda driver: None)

    assert activity_browse._fill_signup_text_field_by_placeholder(
        FakeDriver(),
        "请输入报名人姓名",
        "自动化报名测试",
    )
    assert filled == ["自动化报名测试"]


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


def test_fill_activity_signup_form_accepts_selected_self_registration(monkeypatch):
    draft = activity_browse.build_activity_signup_draft()
    calls = []

    class FakeDriver:
        @property
        def page_source(self):
            return (
                "活动报名 8月05日 周三 - 8月05日 周三 09:50 - 18:50 "
                "集合地点 张家界国家森林公园 活动名额 剩余 19 / 20 "
                "服务配置 领骑 补给车 保险 报名信息 本人 "
                "报名规则 取消规则 报名说明 报名费用 ¥0.01 / 人 提交订单"
            )

    monkeypatch.setattr(
        activity_browse,
        "_fill_signup_text_field_by_placeholder",
        lambda *args, **kwargs: calls.append(args) or False,
        raising=False,
    )

    snapshot = activity_browse.fill_activity_signup_form(FakeDriver(), draft, timeout=3)

    assert snapshot.self_registration_selected
    assert snapshot.is_basic_signup_complete()
    assert calls == []


def test_parse_activity_order_snapshot_detects_payment_center():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="支付中心" visible="true" />
      <XCUIElementTypeStaticText name="订单支付" visible="true" />
      <XCUIElementTypeStaticText name="报名费用 ¥0.01" visible="true" />
      <XCUIElementTypeStaticText name="微信支付" visible="true" />
      <XCUIElementTypeStaticText name="支付宝" visible="true" />
      <XCUIElementTypeStaticText name="去支付" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_activity_order_snapshot(page_source)

    assert snapshot.payment_page_visible
    assert snapshot.payment_method_visible
    assert snapshot.amount_visible
    assert snapshot.payment_action_visible
    assert snapshot.is_order_submission_complete()


def test_activity_signup_already_exists_is_detected():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="已经报名，无需重复报名。" visible="true" />
    </AppiumAUT>
    """

    assert activity_browse.activity_signup_already_exists(page_source)


def test_parse_my_activity_signup_snapshot_detects_pending_signup_status():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的活动" visible="true" />
      <XCUIElementTypeStaticText name="发布" visible="true" />
      <XCUIElementTypeStaticText name="报名" visible="true" />
      <XCUIElementTypeOther name="张家界大环线2天1晚 8月04日 周二 09:25 待支付 支付报名费 ¥0.01" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_my_activity_signup_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.signup_tab_visible
    assert snapshot.registration_visible
    assert snapshot.status == "待支付"
    assert snapshot.payment_action_visible
    assert snapshot.is_signup_status_visible()


def test_open_my_activity_signup_status_taps_me_activity_and_signup_tab(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def tap_me(driver):
        calls.append("me")
        page["source"] = "我的 编辑资料 设置 我的活动 草稿箱"
        return True

    def tap_entry(driver):
        calls.append("my-activity")
        page["source"] = "我的活动 发布 报名 点赞 收藏"
        return True

    def tap_signup_tab(driver):
        calls.append("signup-tab")
        page["source"] = "我的活动 发布 报名 张家界大环线2天1晚 待支付 支付报名费 ¥0.01"
        return True

    monkeypatch.setattr(activity_browse, "_tap_me_tab", tap_me, raising=False)
    monkeypatch.setattr(activity_browse, "_tap_my_activity_entry", tap_entry, raising=False)
    monkeypatch.setattr(activity_browse, "_tap_my_activity_signup_tab", tap_signup_tab, raising=False)
    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    snapshot = activity_browse.open_my_activity_signup_status(FakeDriver(), timeout=3)

    assert snapshot.status == "待支付"
    assert calls == ["me", "my-activity", "signup-tab"]


def test_parse_my_activity_reaction_snapshot_detects_liked_tab_with_empty_state():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的活动" visible="true" />
      <XCUIElementTypeStaticText name="报名" visible="true" />
      <XCUIElementTypeStaticText name="点赞" visible="true" />
      <XCUIElementTypeStaticText name="收藏" visible="true" />
      <XCUIElementTypeStaticText name="暂无点赞活动" visible="true" />
    </AppiumAUT>
    """

    snapshot = activity_browse.parse_my_activity_reaction_snapshot(page_source, tab_name="点赞")

    assert snapshot.page_visible
    assert snapshot.tab_visible
    assert snapshot.empty_state_visible
    assert snapshot.is_basic_reaction_list_visible()


def test_open_my_activity_reaction_list_taps_requested_tab(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def tap_me(driver):
        calls.append("me")
        page["source"] = "我的 编辑资料 设置 我的活动 草稿箱"
        return True

    def tap_entry(driver):
        calls.append("my-activity")
        page["source"] = "我的活动 报名 点赞 收藏 发布"
        return True

    def tap_reaction_tab(driver, tab_name):
        calls.append(("reaction-tab", tab_name))
        page["source"] = f"我的活动 报名 点赞 收藏 暂无{tab_name}活动"
        return True

    monkeypatch.setattr(activity_browse, "_tap_me_tab", tap_me, raising=False)
    monkeypatch.setattr(activity_browse, "_tap_my_activity_entry", tap_entry, raising=False)
    monkeypatch.setattr(activity_browse, "_tap_my_activity_reaction_tab", tap_reaction_tab, raising=False)
    monkeypatch.setattr(activity_browse.time, "sleep", lambda seconds: None)

    snapshot = activity_browse.open_my_activity_reaction_list(FakeDriver(), tab_name="点赞", timeout=3)

    assert snapshot.is_basic_reaction_list_visible()
    assert calls == ["me", "my-activity", ("reaction-tab", "点赞")]
