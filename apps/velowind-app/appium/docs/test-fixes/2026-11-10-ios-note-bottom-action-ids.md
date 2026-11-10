# 2026-11-10 iOS 笔记底部互动标识导致点赞定位失败

## 范围与当前状态

- 用户要求：修复链接报告中的失败。
- 用例：`tests/message/test_ios_message_browse.py::test_logged_in_user_can_browse_comment_and_interact_with_note`。
- 模块：`velowind_appium/modules/message_detail.py::_ios_bottom_action_entries`。
- 平台：iOS 真机，原报告 iPhone 17 / iOS 26.2.1；App 版本未核实。
- 当前状态：42 项定向单元通过；原完整用例真机 1 passed，7 步全部通过；完整 helpers 为 232 passed / 5 项已有 mock 失败，已做基线复核。
- 最后核实：2026-11-10。
- 历史参考：[短内容解析](2026-10-10-ios-short-note-content.md)、[分享面板可见性](2026-10-19-share-sheet-visibility.md)。同一用例，但本次失败在点赞点击前，不是标题解析或分享面板。

## 失败证据

- 原运行：`20261109-174955-98455`；报告目录 `.tmp/appium-ios/runs/20261109-174955-98455/allure-report/`。
- 临时 URL：<http://127.0.0.1:49485/#suites/b7c906346c289b3cab0da2ebee91532b/968048124d5d937f/>。
- `05-like-note`：`AssertionError: Unable to tap bottom action at index 0`，评论步骤 passed；收藏和分享未执行。
- 原截图：`data/attachments/1a08f01c8d374449.png`；XML：`data/attachments/aa97d853dda0aa28.xml`。
- 截图可确认详情及底部互动栏可见，没有键盘遮挡；评论显示“不错 / 刚刚”。截图不证明服务端持久化或清理完成。
- XML：三个 action 的 name 为 `post-detail-bottom-{like,favorite,comment}-action`，label 分别 `2/1/1`；bounds 为 x=204/269/334、y=796、width=55、height=26。数字子节点 width=27，不满足旧容器宽度筛选条件。
- 原 AI 诊断因缺少完整实现和截图/XML内容标为 needs_human，并记录运行期间源码变化；本轮读取原附件并与 HEAD、当前工作区分别对照。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：HEAD 的解析器以 `_source_element_text` 优先取 name，再要求纯数字。新版容器 name 为固定标识，数字在 label 中，因此三个容器被全部丢弃。
- 原 XML 离线核验：HEAD `_ios_bottom_action_entries` 返回 `[]`；当前工作区返回三个正确计数及 bounds。
- 开始本轮前，工作区已有读取三个固定标识及 label 的未提交修补；保留该修补及其他已有改动，不将其声称为本轮新写。
- 仍待核实：原运行精确加载源码；源码曾在原运行期间变化，不推断原运行实际加载了当前修补。本轮完整交互结果已通过。

### 修改

- 保留 `message_detail.py` 现有修补：在可见详情页优先按三个固定 action 标识读取 label 中的数字及实际坐标，保留旧版数字容器兼容路径。
- 新增 `tests/unit-test/test_ios_note_action_ids.py`：使用去除用户内容的最小失败层级，覆盖点赞/收藏、不同底栏高度、计数中心重试、隐藏/禁用拒绝点击，以及点击后计数不变仍失败。
- 不修改原用例、计数变化断言、等待时间、清理行为或业务代码。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium VW_APPIUM_TRIAGE_ENABLED=false VW_APPIUM_AUTO_OPEN_REPORT=false VW_APPIUM_RUN_ID=20261110-note-action-unit .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_ios_note_action_ids.py apps/velowind-app/appium/tests/unit-test/test_ios_p1_performance.py -q --tb=short
PYTHONPATH=apps/velowind-app/appium VW_APPIUM_TRIAGE_ENABLED=false VW_APPIUM_AUTO_OPEN_REPORT=false VW_APPIUM_RUN_ID=20261110-note-action-helpers .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q --tb=short
PYTHONPATH=apps/velowind-app/appium VW_IOS_TARGET=device VW_IOS_UDID=00008150-0006799C2693401C VW_APPIUM_RUN_ID=20261110-note-action-full VW_APPIUM_TRIAGE_ENABLED=false VW_APPIUM_AUTO_OPEN_REPORT=false VW_APPIUM_CAPTURE_EACH_STEP=true .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_ios_message_browse.py::test_logged_in_user_can_browse_comment_and_interact_with_note -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261110-note-action-full/allure-results
```

- 单元：新增测试及现有性能回归共 42 passed；完整 message helpers 为 232 passed / 5 failed（29.61 秒）。5 项均为发布视频旧 mock 缺少 `_api_note_publication` / `find_element`；将本次唯一模块差异 `_ios_bottom_action_entries` 在独立 Python 进程中替换为 HEAD 实现后重跑这 5 项，仍 5 failed / 232 deselected（0.59 秒），确认与本次修补无关。未修改或隐藏这些失败。
- 新增回归的基线反证：独立进程换回 HEAD 解析器后，4 个点赞/收藏定位组合及计数中心重试全部失败（5 failed / 3 deselected，0.34 秒）；修补后的新增 8 项全部通过。
- 离线日志：`.tmp/appium-ios/runs/20261110-note-action-unit/logs/velowind-note-action-{helpers,baseline,regression-baseline}.log`。基线均通过 AST 在独立进程内替换函数，无磁盘源码变动，不影响运行中的真机。
- 真机：启动前未见其他 pytest 或修复执行器占用；复用已有 4723 Appium，指定原设备；`20261110-note-action-full` 最终 **1 passed**，162.08 秒；准备首页、打开首篇、浏览、评论、点赞、收藏、分享 7 步全部 passed，保留原断言。点赞 23.1 秒、收藏 23.5 秒，包含原计数重试等待，未做耗时优化。
- 报告已生成并打开：<http://127.0.0.1:59726/>；本地 HTML 在 `.tmp/appium-ios/runs/20261110-note-action-full/allure-report/`。
- 报告与日志：`.tmp/appium-ios/runs/20261110-note-action-full/{allure-results,pytest.log}`。
- 清理：原用例无自动回滚评论、点赞、收藏及分享；原失败已有评论，本轮清理未执行，不能声明已清理。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 按数字 name + 容器宽度找底部操作 | 旧版没有固定 action 标识 | 新版 name 改为标识，匹配失败；子数字宽度不足，无法兜底 |
| 固定 action 标识 + label 数字 + 实际 bounds | 新版详情层级 | 原 XML 离线核验定位正确，定向单元及完整真机用例通过 |
| 延长超时 | 元素异步出现 | 本次元素已经可见，无法修正名称匹配问题，未采用 |

## 遗留项与交接

- 已完成：原失败证据核对、HEAD 与工作区对比、新增回归覆盖、完整真机验证、helpers 基线复核、报告生成、索引状态更新及 `git diff --check`。
- 真机附件：第 6 步 `6567cf85-f583-4935-a13a-93bf68ebf412-attachment.png` 已目视核验，仍为同一标题详情，显示评论数 2、点赞数 1、收藏数 0；用例允许切换原已收藏状态，计数下降同样符合原断言。
- 第 7 步 passed 仅表明原分享流程及返回信号通过，未另行查询朋友圈发表记录。
- 下次操作：如需整套结论，另跑 suite；若需回滚互动，先核实两轮评论及点赞/收藏当前状态，防止删除错误数据。
- 当前设备占用：本轮 pytest 已退出；原 Appium 和只观察队列的 worker 保留，未结束他人进程。
- 整套未重跑；评论/互动/分享数据未清理。

报告生成命令：

```bash
allure generate .tmp/appium-ios/runs/20261110-note-action-full/allure-results --clean -o .tmp/appium-ios/runs/20261110-note-action-full/allure-report
allure open .tmp/appium-ios/runs/20261110-note-action-full/allure-report --port 0
git diff --check
```
