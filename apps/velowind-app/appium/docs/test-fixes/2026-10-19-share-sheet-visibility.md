# 2026-10-19 朋友圈分享面板可见性误判

## 范围与当前状态

- 用户要求：修复所有自动化 case。
- 用例：`test_logged_in_user_can_browse_comment_and_interact_with_note`；iPhone 17 / App 1.3.0 build 64 / dev-api。
- 当前状态：离线修复已复验，相关合并单元 231 passed / 5 deselected，真机复验待执行；最后核实 2026-10-19。
- 历史参考：[微信登录前置条件](2026-09-16-android-moments-login.md)。本次截图仍在 App 详情，未发现微信登录页，不能套用旧原因。

## 失败证据

- 运行 `20261019-device-test-full-r1`；`07-share-note-to-moments` 57 秒失败，`Unable to confirm the Moments share`。
- 目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/allure-results/`：截图 `d9e2bfc4-d90b-490f-968c-9810b32d57f4-attachment.png`，XML `2206cc35-7d81-4e8d-a157-ba9b7cbd46f5-attachment.xml`。
- 实际为“保障车”详情，图片、标题、正文及互动栏均可见，未见分享面板。
- 离线：旧 `_share_sheet_visible` 为 True；`parse_detail_snapshot` 有正确标题、正文、评论与互动计数，详情 shell 为 True。汇总祖先的可访问性文本包含“微信”，导致错误认为面板未关闭。

## 第 1 轮：分析、修改与验证

### 修改

- `_share_sheet_visible` 解析 XML，继承祖先 visible/displayed 隐藏状态，只接受精确的分享目标名称，不做整份 XML 子串检索。
- 不以返回详情证明真实朋友圈发表成功；保留现有用例的分享流程及断言，实际分享行为需复跑核实。
- 新增 iOS/Android 可见精确目标、隐藏祖先、汇总标签、普通笔记及无效源回归覆盖。

### 验证

- 原 XML 离线复验：修复后 `_share_sheet_visible=False`，不再误认仍有面板。
- 首轮完整 helpers：220 passed、5 failed，29.73 秒；失败均为旧发布 mock 对象缺 `_api_note_publication` 或 `find_element`，与[历史](2026-10-10-ios-short-note-content.md)相同，未覆盖原失败结果。
- 基线复核：从 HEAD 提取 `publish_message_note` AST，在当前模块原共享字典中重新编译并替换该函数，pytest 只执行上述 5 条；同样 5 failed / 222 deselected，0.40 秒，日志 `.tmp/appium-ios/share-baseline.log`。
- 合并单元：`test_note_card_picker.py` 与 `test_message_detail_helpers.py`，排除上述 5 个基线已确认的旧 mock 测试后，231 passed / 5 deselected，29.26 秒；命令通过 `-k` 明确排除四个函数名（一个函数参数化为两项）。计时目录 `.tmp/appium-ios/runs/20261019-155856-27805/timing/`。
- 真机：未复跑，等待当前 suite 完成；本用例评论、点赞、收藏已执行，分享后的计数断言未执行。
- 实际清理：交互数据尚未清理或核实，不能记为清理成功。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 在整份 XML 搜索“微信” | 页面可访问性汇总其他页面文字 | 本次误报，须检查具体可见控件 |

## 遗留项与交接

- 当前整套继续收集其他失败；结束后复跑此完整用例并核对真实分享状态。

## 第 2 轮：完整用例真机复验

- 运行 `20261019-device-test-full-r2`，原交互用例 CASE PASSED；7 个步骤均 passed，分享步骤 13.6 秒。
- 该结果包含评论、点赞、收藏、分享流程以及分享后的原计数断言；没有以局部步骤代替整条通过。
- 通过的分享信号仍是原用例的确认流程和返回详情/首页，不额外宣称已查询朋友圈服务端发表记录。
- 实际评论及点赞收藏数据未清理；整套仍在执行。
