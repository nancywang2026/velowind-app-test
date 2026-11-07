# 2026-10-19 系统通知入口文案兼容

## 范围与当前状态

- 用户要求：修复所有自动化 case；用例 `test_user_can_view_system_message_detail`。
- 平台：iPhone 17，App 1.3.0 build 64，dev-api；最后核实 2026-10-19。
- 当前状态：修复后单元验证中，真机复验待执行。索引未找到同类文案变更记录。

## 失败证据

- 运行 `20261019-device-test-full-r1`，报告目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- `02-open-system-message-page` 30.4 秒失败：`Messages page did not expose the System Messages entry`。
- 截图 `allure-results/e5412522-6d8c-416f-a231-08004f5f4e5e-attachment.png`；XML `22cb4824-b204-4049-9e4f-a3eb36a2e217-attachment.xml`。
- 当前消息页明确显示“系统通知”，旧代码只等待和点击“系统消息”。

## 第 1 轮：分析、修改与验证

- 已确认原因：等待及点击文案不匹配。
- 修改 `message_detail.py`：入口等待、点击及详情页标题兼容“系统消息”与“系统通知”；保留类别、时间、标题、正文的就绪判断。
- 对已有入口及解析单元分别参数化两种文案；与分享/卡片合并验证 231 passed / 5 deselected（29.26 秒）；5 个排除项为 HEAD 基线同样失败的旧发布 mock，详见[分享记录](2026-10-19-share-sheet-visibility.md)。
- 真机：未复跑，等待当前 suite 完成。
- 实际清理：本用例只读，无新增业务数据。
- 无失败修改尝试；后续实际通知列表结构仍须真机核实，不能仅凭更名就宣称完整通过。

## 遗留项与交接

- 复跑完整系统消息用例并核实通知时间及内容字段。
