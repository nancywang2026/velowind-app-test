# Message Module Appium Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the iOS Appium suite by functional test packages and add a message-browsing automation case for a normal user flow.

**Architecture:** Keep the existing pytest/Appium/Allure runtime intact while splitting test files into module-oriented packages under `tests/`. Add focused message-flow helpers under `velowind_appium/modules/` so the test case remains declarative and future message scenarios can reuse the same selectors and parsing logic.

**Tech Stack:** Python, pytest, Appium, Selenium WebDriver, Allure

---

### Task 1: Reshape the test tree into functional packages

**Files:**
- Create: `apps/velowind-app/appium/tests/smoke/__init__.py`
- Create: `apps/velowind-app/appium/tests/message/__init__.py`
- Modify: `apps/velowind-app/appium/velowind_appium/run_ios_tests.py`
- Modify: `apps/velowind-app/appium/tests/conftest.py`
- Move: `apps/velowind-app/appium/tests/test_ios_feature_walkthrough.py` to `apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py`

- [ ] **Step 1: Move the walkthrough smoke test into the smoke package**

```text
Source: apps/velowind-app/appium/tests/test_ios_feature_walkthrough.py
Target: apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py
```

- [ ] **Step 2: Update the test runner to target the full tests directory**

```python
TEST_PATH = REPO_ROOT / "apps" / "velowind-app" / "appium" / "tests"
```

- [ ] **Step 3: Update the Allure auto-open guard to match the relocated smoke file**

```python
WALKTHROUGH_TEST_FILE = "smoke/test_ios_feature_walkthrough.py"
```

- [ ] **Step 4: Keep package directories importable**

```python
# apps/velowind-app/appium/tests/smoke/__init__.py
# apps/velowind-app/appium/tests/message/__init__.py
```

- [ ] **Step 5: Run a collection check**

Run: `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests --collect-only -q`
Expected: smoke tests are collected from `tests/smoke/...`

### Task 2: Add reusable message-module helpers

**Files:**
- Create: `apps/velowind-app/appium/velowind_appium/modules/__init__.py`
- Create: `apps/velowind-app/appium/velowind_appium/modules/home_feed.py`
- Create: `apps/velowind-app/appium/velowind_appium/modules/message_detail.py`
- Modify: `apps/velowind-app/appium/velowind_appium/actions.py`
- Test: `apps/velowind-app/appium/tests/test_message_detail_helpers.py`

- [ ] **Step 1: Write helper-focused tests for page-source parsing**

```python
def test_parse_detail_snapshot_extracts_title_counts_and_comments():
    page_source = """
    标题 春日骑行
    浏览 128
    评论 3
    正文 这是内容
    留言 用户A：不错
    图票 查看图票
    """
    snapshot = parse_detail_snapshot(page_source)
    assert snapshot.title == "春日骑行"
    assert snapshot.view_count == "128"
    assert snapshot.comment_count == "3"
```

- [ ] **Step 2: Run the helper tests to see the initial failure**

Run: `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/test_message_detail_helpers.py -q`
Expected: FAIL because the new module does not exist yet

- [ ] **Step 3: Implement minimal parsing and interaction helpers**

```python
@dataclass
class MessageDetailSnapshot:
    title: str | None
    body: str | None
    view_count: str | None
    comment_count: str | None
    comments: list[str]
    ticket_texts: list[str]
```

- [ ] **Step 4: Add a generic vertical swipe helper for the home feed**

```python
def swipe_vertical(driver: WebDriver, direction: str = "up") -> None:
    driver.execute_script("mobile: swipe", {"direction": direction})
```

- [ ] **Step 5: Re-run the helper tests**

Run: `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/test_message_detail_helpers.py -q`
Expected: PASS

### Task 3: Add the message browsing automation case

**Files:**
- Create: `apps/velowind-app/appium/tests/message/test_ios_message_browse.py`
- Modify: `apps/velowind-app/appium/README.md`

- [ ] **Step 1: Write the message-module Appium test around the requested flow**

```python
@pytest.mark.full
def test_normal_user_can_browse_and_comment_message(driver, step):
    ...
```

- [ ] **Step 2: Implement the flow with reusable helpers**

```python
step("open-first-message", lambda: open_first_home_message(driver))
snapshot = step("read-message-detail", lambda: read_message_detail_snapshot(driver))
step("write-comment", lambda: submit_message_comment(driver, "自动化测试留言"))
step("toggle-ticket-copy", lambda: toggle_ticket_text_and_assert_change(driver))
```

- [ ] **Step 3: Document the new package layout and test target**

```markdown
- `tests/smoke/`: 快速巡检
- `tests/message/`: 消息/资讯浏览模块
```

- [ ] **Step 4: Run a targeted non-device-safe validation command**

Run: `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/test_message_detail_helpers.py apps/velowind-app/appium/tests --collect-only -q`
Expected: PASS for helper tests and successful collection for module packages

- [ ] **Step 5: Run the real-device case when Appium/device are available**

Run: `PYTHONPATH=apps/velowind-app/appium python3 -m pytest apps/velowind-app/appium/tests/message/test_ios_message_browse.py -q -m full`
Expected: The message browsing scenario runs on a connected iOS device and produces Allure attachments
