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
