# 2026-11-06 iOS 发布后详情标题标识被当作文字

## 范围与当前状态

- 用户要求：排查再次失败的图片发布用例。
- 用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`。
- 模块：`message_detail.py` 发布后详情身份核验、我的笔记页面识别。
- 平台：iOS 真机，bundle `com.velowind.rider`；本轮未核实 App / 系统版本。
- 当前状态：已修正，22 项定向单元通过；修复后真机成功打开原笔记并核验标题。完整发布用例未重跑，原笔记未清理。
- 历史参考：[发布详情误选与清理](2026-09-15-ios-publish-cleanup.md)、[短标题内容读取](2026-10-10-ios-short-note-content.md)、[端口不一致](2026-11-06-appium-server-port.md)。本次服务已连通，失败原因独立于端口。
- 最后核实时间：2026-11-06（Asia/Shanghai）。

## 失败证据

- 原报告运行 `20261106-113148-19720`，目录 `.tmp/appium-ios/runs/20261106-113148-19720/`。
- URL：`http://127.0.0.1:53191/#suites/a315921332822b24a92de7455c3da80b/fb6e77ba456cbe93/`。
- driver、登录和准备步骤通过；发布步骤 failed：`Unable to open published note detail from My Notes for title: 2596f1eb-测试 - 长白山真的有`。
- 原 PNG：`allure-report/data/attachments/ae8ffb2da99a14c7.png`；XML：`allure-report/data/attachments/8cc43d2a6228f07e.xml`。
- 截图确认“我的笔记”右上已有目标图片笔记，XML 对应可见卡片 ID `post-home-feed-note-card-pst-76a7791030c94ef8b1fc9e63f6561afa`。
- post ID 附件确认目标 `pst-76a7791030c94ef8b1fc9e63f6561afa`；原报告未到清理步骤，不能称已删除。

## 第 1 轮：原逻辑现场复查（失败保留）

### 分析与验证

- 启动前检查无 pytest；保留现有 Appium 4723 和 WDA，不结束其他进程。
- 临时脚本 `.tmp/appium-ios/published-note-open-debug/probe.py` 新建会话，调用原 `_open_published_note_detail_from_my_notes`，只尝试打开既有笔记，不重复发布。
- 命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python .tmp/appium-ios/published-note-open-debug/probe.py`，日志同目录 `probe.log`。
- 结果：失败，仍抛相同断言；`after.xml` 却确认已在目标 `post-detail-page`，标题节点 `name="post-detail-title"`，`label` / `value` 为正确目标标题。
- 已确认原因：`_ios_published_detail_title` 调用通用 `_source_element_text`，优先读取 name，把控件标识当标题，拒绝正确详情并返回列表。
- 另确认：原失败 XML 的 `_my_notes_list_visible` 返回 false；新版“我发的／收藏的／赞过的”不在识别范围。
- 无效尝试：原逻辑现场打开既有笔记仍失败；不通过延长超时或重复发布解决。
- 会话已退出。原配置 `no_reset=false`；下一轮显式保留 App 状态。

## 第 2 轮：修改与验证

### 修改

- `_ios_published_detail_title` 优先显式 `post-detail-title` 节点，按 label / value 读取实际文字；没有该标识的旧版本保留 StaticText 匹配路径。
- 显式标题不匹配时，不以正文中的目标标题作为匹配证据。
- `_my_notes_list_visible` 兼容新版三个 Tab 文案。
- 添加 4 项回归（含参数化）；保留原标题核验、图片比对与清理断言。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium VW_APPIUM_AUTO_OPEN_REPORT=false .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q -k 'published_detail or my_notes_list_visible or published_note_title_rect or ios_published_card or publish_success'
```

- 单元：22 passed、215 deselected，0.16 秒；既有 LibreSSL warning。
- 修复后真机：通过。执行 `VW_IOS_NO_RESET=true PYTHONPATH=apps/velowind-app/appium .venv/bin/python .tmp/appium-ios/published-note-open-debug/probe.py`，退出码 0，日志 `probe-fixed.log` 输出 `detail opened`。同目录 `after.xml` / `after.png` 确认目标标题与图片详情；第 1 轮 XML / PNG 另保存在 `baseline/`，失败日志 `probe.log` 保留。未重复发布。
- 消息助手全文件回归：`PYTHONPATH=apps/velowind-app/appium VW_APPIUM_AUTO_OPEN_REPORT=false .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q`，232 passed、5 failed，29.68 秒。五项失败为发布流程 mock 缺 `_api_note_publication` 或 `find_element`，与历史短标题记录中列出的五项相同；本轮未重做基线隔离验证，不计全文件通过。run `20261106-114116-20404`。
- 本次修改文件的 `git diff --check` 通过。
- 完整发布用例：未重跑。
- 清理：原失败笔记尚未执行删除，本轮调查未新增笔记。

## 可复用方法与无效尝试

| 方法 | 条件 | 结果 |
| --- | --- | --- |
| 对照已打开详情的 XML 中 name / label / value | 控件新增稳定标识 | 本轮明确 name 为标识、label/value 为文字 |
| 仅用原“我的笔记”失败截图判断未打开 | 超时循环可能打开后又返回 | 不足；本轮现场 after.xml 证明能够打开 |

## 遗留项与交接

- 已完成：使用 `VW_IOS_NO_RESET=true` 重新运行同一只读打开探测，真机目标标题身份核验通过，会话已退出。
- 下一步：完整重跑原发布用例，分别核对图片比对、用例断言和实际清理结果。
- 未验证完整发布、图片比对、API 删除；原笔记清理待处理，不计为清理成功。
