from velowind_appium.modules import profile


def test_parse_profile_snapshot_detects_readonly_profile_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="个人资料" visible="true" />
      <XCUIElementTypeStaticText name="头像" visible="true" />
      <XCUIElementTypeStaticText name="昵称" visible="true" />
      <XCUIElementTypeStaticText name="手机号" visible="true" />
      <XCUIElementTypeStaticText name="实名认证" visible="true" />
      <XCUIElementTypeStaticText name="生日" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_profile_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.avatar_visible
    assert snapshot.nickname_visible
    assert snapshot.phone_visible
    assert snapshot.real_name_status_visible
    assert snapshot.birthday_visible
    assert snapshot.is_basic_profile_visible()


def test_parse_profile_snapshot_detects_avatar_image_without_avatar_label():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="个人资料" visible="true" />
      <XCUIElementTypeOther name="Nancy" visible="true">
        <XCUIElementTypeImage visible="true" x="159" y="132" width="84" height="84" />
      </XCUIElementTypeOther>
      <XCUIElementTypeOther name="昵称 Nancy 手机号 133****9990 实名认证状态 已实名 生日 1983-02-12" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_profile_snapshot(page_source)

    assert snapshot.avatar_visible
    assert snapshot.is_basic_profile_visible()


def test_open_profile_page_uses_me_entry_and_waits_for_profile(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def open_me_page(driver, timeout=12):
        calls.append(("open-me", timeout))
        page["source"] = "我的 编辑资料 设置 个人资料 我的活动"

    def tap_profile_entry(driver):
        calls.append(("profile-entry",))
        page["source"] = "个人资料 头像 昵称 手机号 实名认证 生日"
        return True

    monkeypatch.setattr(profile.draft_flow, "open_me_page", open_me_page)
    monkeypatch.setattr(profile, "_tap_profile_entry", tap_profile_entry)
    monkeypatch.setattr(profile.time, "sleep", lambda seconds: None)

    snapshot = profile.open_profile_page(FakeDriver(), timeout=5)

    assert snapshot.is_basic_profile_visible()
    assert calls == [("open-me", 5), ("profile-entry",)]


def test_parse_interest_preferences_snapshot_detects_sport_options():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="兴趣偏好" visible="true" />
      <XCUIElementTypeStaticText name="骑行" visible="true" />
      <XCUIElementTypeStaticText name="徒步" visible="true" />
      <XCUIElementTypeStaticText name="登山" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_interest_preferences_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.visible_options == ["骑行", "徒步", "登山"]
    assert snapshot.is_basic_preferences_visible()


def test_open_interest_preferences_page_taps_me_entry_and_waits(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def open_me_page(driver, timeout=12):
        calls.append(("open-me", timeout))
        page["source"] = "我的 个人资料 兴趣偏好 我的活动"

    def tap_interest_entry(driver):
        calls.append(("interest-entry",))
        page["source"] = "兴趣偏好 骑行 徒步 登山"
        return True

    monkeypatch.setattr(profile.draft_flow, "open_me_page", open_me_page)
    monkeypatch.setattr(profile, "_tap_interest_preferences_entry", tap_interest_entry, raising=False)
    monkeypatch.setattr(profile.time, "sleep", lambda seconds: None)

    snapshot = profile.open_interest_preferences_page(FakeDriver(), timeout=5)

    assert snapshot.is_basic_preferences_visible()
    assert calls == [("open-me", 5), ("interest-entry",)]


def test_parse_my_coupons_snapshot_detects_coupon_status_tabs():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的卡券" visible="true" />
      <XCUIElementTypeStaticText name="未使用" visible="true" />
      <XCUIElementTypeStaticText name="已使用" visible="true" />
      <XCUIElementTypeStaticText name="已失效" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_my_coupons_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.visible_statuses == ["未使用", "已使用", "已失效"]
    assert snapshot.is_basic_coupons_visible()


def test_open_my_coupons_page_taps_me_entry_and_waits(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def open_me_page(driver, timeout=12):
        calls.append(("open-me", timeout))
        page["source"] = "我的 我的卡券 个人资料 兴趣偏好"

    def tap_coupons_entry(driver):
        calls.append(("coupons-entry",))
        page["source"] = "我的卡券 未使用 已使用 已失效"
        return True

    monkeypatch.setattr(profile.draft_flow, "open_me_page", open_me_page)
    monkeypatch.setattr(profile, "_tap_my_coupons_entry", tap_coupons_entry, raising=False)
    monkeypatch.setattr(profile.time, "sleep", lambda seconds: None)

    snapshot = profile.open_my_coupons_page(FakeDriver(), timeout=5)

    assert snapshot.is_basic_coupons_visible()
    assert calls == [("open-me", 5), ("coupons-entry",)]


def test_parse_account_security_snapshot_detects_readonly_security_fields():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="账号与安全" visible="true" />
      <XCUIElementTypeStaticText name="绑定手机号" visible="true" />
      <XCUIElementTypeStaticText name="133****9990" visible="true" />
      <XCUIElementTypeStaticText name="登录状态" visible="true" />
      <XCUIElementTypeStaticText name="已登录" visible="true" />
      <XCUIElementTypeStaticText name="设置/修改密码" visible="true" />
      <XCUIElementTypeStaticText name="实名认证" visible="true" />
      <XCUIElementTypeStaticText name="已认证" visible="true" />
      <XCUIElementTypeStaticText name="账号注销" visible="true" />
      <XCUIElementTypeStaticText name="危险操作，需通过短信验证码完成确认" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_account_security_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.phone_visible
    assert snapshot.login_status_visible
    assert snapshot.password_entry_visible
    assert snapshot.real_name_status_visible
    assert snapshot.account_deletion_warning_visible
    assert snapshot.is_basic_account_security_visible()


def test_open_account_security_page_taps_settings_and_security_entry(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def open_me_page(driver, timeout=12):
        calls.append(("open-me", timeout))
        page["source"] = "我的 我的活动 我的卡券 个人资料 兴趣偏好"

    def tap_settings_entry(driver):
        calls.append(("settings-entry",))
        page["source"] = "设置 语言 · 简体中文 账号与安全 个人资料 成为领队 退出登录"
        return True

    def tap_account_security_entry(driver):
        calls.append(("account-security-entry",))
        page["source"] = "账号与安全 绑定手机号 133****9990 登录状态 已登录 设置/修改密码 实名认证 已认证 账号注销 危险操作"
        return True

    monkeypatch.setattr(profile.draft_flow, "open_me_page", open_me_page)
    monkeypatch.setattr(profile, "_tap_settings_entry", tap_settings_entry, raising=False)
    monkeypatch.setattr(profile, "_tap_account_security_entry", tap_account_security_entry, raising=False)
    monkeypatch.setattr(profile.time, "sleep", lambda seconds: None)

    snapshot = profile.open_account_security_page(FakeDriver(), timeout=5)

    assert snapshot.is_basic_account_security_visible()
    assert calls == [("open-me", 5), ("settings-entry",), ("account-security-entry",)]


def test_parse_leader_application_snapshot_detects_readonly_status():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="成为领队" visible="true" />
      <XCUIElementTypeStaticText name="寻风集领队，等你加入" visible="true" />
      <XCUIElementTypeStaticText name="领队培训、标准流程、品牌背书、资源对接" visible="true" />
      <XCUIElementTypeStaticText name="温馨提示" visible="true" />
      <XCUIElementTypeStaticText name="提交申请后，我们会结合你的骑行经验、活动组织能力与资料完整度进行审核" visible="true" />
      <XCUIElementTypeStaticText name="申请状态" visible="true" />
      <XCUIElementTypeStaticText name="您已经成为领队" visible="true" />
    </AppiumAUT>
    """

    snapshot = profile.parse_leader_application_snapshot(page_source)

    assert snapshot.page_visible
    assert snapshot.introduction_visible
    assert snapshot.benefits_visible
    assert snapshot.notice_visible
    assert snapshot.status_visible
    assert snapshot.is_basic_leader_application_visible()


def test_open_leader_application_page_taps_settings_and_leader_entry(monkeypatch):
    calls = []
    page = {"source": "首页 活动 消息 我的"}

    class FakeDriver:
        @property
        def page_source(self):
            return page["source"]

    def open_me_page(driver, timeout=12):
        calls.append(("open-me", timeout))
        page["source"] = "我的 我的活动 我的卡券 个人资料 兴趣偏好"

    def tap_settings_entry(driver):
        calls.append(("settings-entry",))
        page["source"] = "设置 账号与安全 个人资料 成为领队 退出登录"
        return True

    def tap_leader_application_entry(driver):
        calls.append(("leader-entry",))
        page["source"] = "成为领队 寻风集领队，等你加入 领队培训 标准流程 温馨提示 提交申请后 申请状态 您已经成为领队"
        return True

    monkeypatch.setattr(profile.draft_flow, "open_me_page", open_me_page)
    monkeypatch.setattr(profile, "_tap_settings_entry", tap_settings_entry, raising=False)
    monkeypatch.setattr(profile, "_tap_leader_application_entry", tap_leader_application_entry, raising=False)
    monkeypatch.setattr(profile.time, "sleep", lambda seconds: None)

    snapshot = profile.open_leader_application_page(FakeDriver(), timeout=5)

    assert snapshot.is_basic_leader_application_visible()
    assert calls == [("open-me", 5), ("settings-entry",), ("leader-entry",)]
