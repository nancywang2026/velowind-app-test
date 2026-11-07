# 2026-10-19 活动分类“全部”文案兼容

## 范围与当前状态

- 用例 `test_user_can_filter_activities_by_cycling`；用户要求整套通过。
- iPhone 17 / App 1.3.0 build 64 / dev-api；最后核实 2026-10-19；当前单元运行中，真机复验待执行。
- 历史索引无同类活动分类更名记录。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- `04-switch-activity-category-navigation` 11.1 秒失败：`Unable to find the activity category navigation`。
- XML `allure-results/438838c6-1484-4b66-bec2-67059f3d7517-attachment.xml`；PNG `5364e228-16b2-4673-b090-86da4bff5d8c-attachment.png`。
- 现场导航为“全部、骑行、徒步…”，原代码强制要求“全部活动”。

## 第 1 轮：修改与验证

- `activity_browse.py` 的分类导航等待兼容可见精确文本“全部”，保留旧“全部活动”和分类项检查。
- 新增两种文案单元覆盖；执行 `VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_browse_helpers.py -q`，45 passed，1.51 秒。
- 真机：未复跑；只读用例，无新增业务数据或清理。
- 无失败实现尝试；不修改骑行分类结果必须全部匹配的断言。

## 遗留项

- 统一 60 快照深度下复跑完整分类用例。
