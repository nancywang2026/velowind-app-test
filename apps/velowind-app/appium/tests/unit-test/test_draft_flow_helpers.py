from velowind_appium.modules import draft_flow


def test_save_draft_dialog_is_visible_detects_prompt_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="是否保存草稿" />
      <XCUIElementTypeStaticText name="保存草稿" />
      <XCUIElementTypeStaticText name="不保存" />
    </AppiumAUT>
    """

    assert draft_flow.save_draft_dialog_is_visible(page_source) is True


def test_me_page_is_visible_detects_profile_text():
    page_source = """
    <AppiumAUT>
      <XCUIElementTypeStaticText name="我的" />
      <XCUIElementTypeStaticText name="编辑资料" />
      <XCUIElementTypeStaticText name="设置" />
    </AppiumAUT>
    """

    assert draft_flow.me_page_is_visible(page_source) is True


def test_fill_note_draft_title_reuses_note_form_and_title_helpers(monkeypatch):
    events = []

    monkeypatch.setattr(draft_flow.message_detail, "wait_for_message_note_form", lambda driver, timeout: events.append(("wait-form", timeout)))
    monkeypatch.setattr(draft_flow.message_detail, "_fill_note_title", lambda driver, title: events.append(("fill-title", title)))
    monkeypatch.setattr(draft_flow.message_detail, "_hide_keyboard", lambda driver: events.append("hide-keyboard"))

    draft_flow.fill_note_draft_title(object(), "草稿标题", timeout=12)

    assert events == [("wait-form", 12), ("fill-title", "草稿标题"), "hide-keyboard"]


def test_save_note_draft_flow_runs_expected_steps(monkeypatch):
    events = []

    monkeypatch.setattr(draft_flow, "open_note_draft_editor", lambda driver, ios_config=None, timeout=30: events.append(("open-editor", timeout)))
    monkeypatch.setattr(draft_flow, "fill_note_draft_title", lambda driver, title, timeout=20: events.append(("fill-title", title, timeout)))
    monkeypatch.setattr(draft_flow, "go_back_from_note_editor", lambda driver, timeout=10: events.append(("go-back", timeout)))
    monkeypatch.setattr(draft_flow, "wait_for_save_draft_dialog", lambda driver, timeout=10: events.append(("wait-dialog", timeout)))
    monkeypatch.setattr(draft_flow, "choose_save_draft", lambda driver, timeout=10: events.append(("save-draft", timeout)))
    monkeypatch.setattr(draft_flow, "open_me_page", lambda driver, timeout=12: events.append(("open-me", timeout)))

    draft_flow.save_note_draft(object(), "草稿标题", ios_config=object(), timeout=18)

    assert events == [
        ("open-editor", 18),
        ("fill-title", "草稿标题", 18),
        ("go-back", 10),
        ("wait-dialog", 10),
        ("save-draft", 10),
        ("open-me", 12),
    ]
