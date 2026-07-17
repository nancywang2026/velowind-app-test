# Zhangjiajie Activity Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Zhangjiajie 2-day/1-night activity publish Appium test that runs through the same case on iOS and Android.

**Architecture:** Keep UI automation in `velowind_appium.modules.activity`, keep test data in `tests/activity/testdata/publish_activity.yaml`, and keep the pytest test file platform-neutral. Android and iOS suite files reference the same test so field coverage stays aligned.

**Tech Stack:** Python, pytest, Appium, YAML, pnpm script wrappers.

---

### Task 1: Make Activity Draft Read All Submitted Fields

**Files:**
- Modify: `apps/velowind-app/appium/tests/unit-test/test_activity_helpers.py`
- Modify: `apps/velowind-app/appium/velowind_appium/modules/activity.py`
- Modify: `apps/velowind-app/appium/tests/activity/testdata/publish_activity.yaml`

- [ ] **Step 1: Write the failing test**

```python
def test_build_activity_draft_reads_all_zhangjiajie_fields():
    draft = build_activity_draft(testdata_path=TESTDATA_PATH)

    assert draft.title == "张家界大环线2天1晚"
    assert draft.activity_type == "骑行"
    assert draft.province == "湖南省"
    assert draft.city == "张家界市"
    assert draft.album == "张家界"
    assert draft.contact_name == "张家界大环线领队"
    assert draft.contact_phone == "13800138000"
    assert draft.location == "张家界西站出站口"
    assert draft.max_participants == "20"
    assert draft.fee == "0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_helpers.py::test_build_activity_draft_reads_all_zhangjiajie_fields -q`

Expected: FAIL because the YAML and builder still use the previous activity and hard-coded optional values.

- [ ] **Step 3: Write minimal implementation**

Update the YAML first case to Zhangjiajie and update `_build_activity_draft_from_case()` so `contactName`, `contactPhone`, `maxParticipants`, and `fee` are read from `advancedOptions` with current defaults as fallback.

- [ ] **Step 4: Run test to verify it passes**

Run the same focused pytest command. Expected: PASS.

### Task 2: Make Publish Activity Test Platform-Neutral

**Files:**
- Move/modify: `apps/velowind-app/appium/tests/activity/test_ios_publish_activity.py`
- Create: `apps/velowind-app/appium/tests/activity/test_publish_activity.py`
- Modify: `apps/velowind-app/appium/test-suites/activity-publish.yaml`
- Create: `apps/velowind-app/appium/test-suites/android-activity-publish.yaml`
- Modify: `scripts/appium-android-local.sh`

- [ ] **Step 1: Write the failing runner/suite tests**

Add unit coverage that `android-activity-publish.yaml` points to `activity/test_publish_activity.py` and that Android local publish mode can route to an activity publish suite.

- [ ] **Step 2: Run focused unit tests to verify failure**

Run: `PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_run_android_tests.py -q`

Expected: FAIL until the suite file and script behavior exist.

- [ ] **Step 3: Write minimal implementation**

Rename the test function to `test_user_can_publish_activity_for_review` in `test_publish_activity.py`, update suite paths, and add an `activity-publish` mode to `scripts/appium-android-local.sh`.

- [ ] **Step 4: Run focused unit tests**

Run: `PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_helpers.py apps/velowind-app/appium/tests/unit-test/test_run_android_tests.py -q`

Expected: PASS.

### Task 3: Run Android Emulator Verification

**Files:**
- Verify: `apps/velowind-app/appium/tests/activity/test_publish_activity.py`
- Verify: `apps/velowind-app/appium/test-suites/android-activity-publish.yaml`

- [ ] **Step 1: Run Android local activity publish suite**

Run: `pnpm appium:android:test:local:activity_publish`

Expected: pytest exit code 0 and the publish activity case passes on the Android emulator.

- [ ] **Step 2: If Android fails, repair with TDD**

For each confirmed helper defect, add a focused unit test in `tests/unit-test/test_activity_helpers.py`, watch it fail, implement the narrow helper fix, rerun the unit test, and rerun the Android activity publish suite.
