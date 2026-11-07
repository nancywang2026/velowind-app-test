# 2026-10-10 iOS 短标题和相同正文误读

## 范围与当前状态

- 用户要求：修复所链接报告中的失败测试用例。
- 用例：`test_logged_in_user_can_browse_comment_and_interact_with_note`。
- 涉及模块：`message_detail.py` 的详情解析；不修改 App 代码。
- 平台：iOS 真机 iPhone 17，设备 `00008150-0006799C2693401C`，iOS 26.2.1；现场 App `com.velowind.rider` 1.2.7 / build 60。
- 当前状态：修复完成；240 项相关单元通过，原失败用例完整真机 1 passed（7 步全部通过）；互动数据未清理。
- 最后核实时间：2026-10-10。
- 历史参考：[详情加载失败](2026-09-21-ios-note-detail-load-failure.md)。详情子树隔离和错误页判断仍适用，但本次截图没有加载错误，不能复用旧故障结论。

## 失败证据

- 原运行 ID：`20261010-113601-76105`；目录 `.tmp/appium-ios/runs/20261010-113601-76105/allure-report/`。
- 临时 URL：<http://127.0.0.1:49475/#suites/b7c906346c289b3cab0da2ebee91532b/9ffa107da28d5bd6/>。
- 原 suite：8 passed、1 failed，共 9 条；不能计为整套通过。
- `02-open-first-note` 失败：`Message detail did not expose all expected fields`；最终快照标题为 `徐汇滨江中心模速空间`，正文为 `None`，评论数为 `0`。
- 截图：报告 `data/attachments/333016a1a2fd362.png`；XML：`data/attachments/a8f5e8c2d1ce902a.xml`。
- 截图确认正在播放视频；标题和正文均为 `测试`，下面是地点和底部互动栏。
- XML 内容面板首个直接 StaticText 是标题 `测试`；下一个 Other 的 StaticText 是正文 `测试`；地点、时间、评论是其他分组。页面同时保留底层页面结构。
- 预期：读取真实标题 / 正文并继续原断言；实际：误读地点为标题，等待 20 秒后失败。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：iOS 仍使用 `_extract_title` 的 4–40 字限制；`测试` 长度不足，后面的地点被选为标题。
- 已确认：`_extract_body` 要求至少 10 字且不能与标题相同，因此短正文及相同标题 / 正文无法可靠读取。
- 已确认：此时页面已正常加载；增大等待时间不能修正解析。
- Android 已有按内容面板读取的逻辑，本次只增加 iOS 对应解析，保留旧层级兼容路径及显式加载失败检查。

### 修改

- `message_detail.py`：新增 `_ios_detail_content`，在 `parse_detail_snapshot` 中接入。iOS 从 `post-detail-scroll-view` 的内容面板读取标题和紧随其后的正文；正文允许直接 StaticText 或单层 / 多层 Other 包裹，保留短内容和重复内容。
- 只检查内容区域的直接面板，不递归把评论作者当标题。已知详情滚动区缺正文时不退回全页猜正文；没有该结构的旧层级保留原兼容解析。
- `test_message_detail_helpers.py`：新增 8 项回归，覆盖短 / 相同 / 长标题和正文、正文缺失 / 为空、评论作者不能冒充内容及读取就绪判断。
- 保留：原用例标题 / 正文、废弃浏览量、评论及互动断言。

### 验证

- 修改前新增回归运行：7 failed，复现地点误作标题及短正文缺失。报告运行 ID `20261010-115201-89565`；第 8 项评论面板隔离回归在后续审查时补入。
- 初轮组合回归：224 passed、5 failed、15 deselected；筛选词 `detail` 同时匹配模块路径，实际也运行了发布 mock。
- 基线复核：将 HEAD 原始 `publish_message_note` 函数载入当前模块、保留 pytest monkeypatch 的共享全局字典，5 项同样失败；报错仍为 mock 对象缺 `_api_note_publication` 或 `find_element`。日志 `.tmp/appium-ios/short-note-fix/baseline-round3.log`。
- 基线脚本无效尝试：第 1 次遗漏 postponed annotations 导致 Python 3.9 类型联合异常；第 2 次使用复制的全局字典，使 monkeypatch 未作用于基线函数，不能用于证明相同失败。日志 `baseline.log`、`baseline-round2.log` 保留，第 3 次修正后才作为基线证据。
- 最终相关回归：240 passed、5 deselected；只排除已复核的 5 条发布 mock，没有将其记为通过。日志 `.tmp/appium-ios/short-note-fix/unit-final.log`；run ID `20261010-ios-short-note-unit-final`。
- 原失败 XML 重放：正确返回标题 `测试`、正文 `测试`、评论数 `0`，无浏览量，详情就绪判断通过。
- 静态检查：`git diff --check` 通过。
- 真机浏览验证：1 passed，40.28 秒；run ID `20261010-ios-short-note-readonly`，目录 `.tmp/appium-ios/runs/20261010-ios-short-note-readonly/`。临时 pytest probe 验证准备首页、打开第一篇、读取详情和原用例全部浏览字段断言，并额外断言标题和正文都为 `测试`。不是完整原用例通过，也不是整套通过。
- 证据：上述目录 `before.xml`、`after.xml`、`after.png`、`result.json` 和 `allure-results/`；日志 `.tmp/appium-ios/short-note-fix/device.log`。
- 清理验证：只读运行，无新增评论 / 点赞 / 收藏 / 分享；不涉及删除。旧数据未清理。
- 本轮结论：修复对原失败 XML 和同一篇真机笔记有效；完整互动流程继续验证。
- 启动前已查进程：未见运行中的 pytest；多个历史 Appium 服务和 WDA 构建进程存在，不结束其他服务。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 对照截图与 XML，按内容分组提取 | 短标题、短正文、相同标题 / 正文 | 当前证据确认长度筛选不适用；待验证结构解析 |
| 增大读取超时 | 真正异步加载 | 本次字段已存在，不能解决解析规则错误；未作为修改实施 |

## 遗留项与交接

- 已完成：原报告、截图、XML 和历史记录核实；确认是测试解析问题。
- 已完成：代码修改、8 项新增回归、240 项相关回归通过、原失败 XML 重放、同一篇真机浏览验证和完整原用例真机复跑。
- 说明原用例包含实际朋友圈发布后，用户再次明确要求“用真机验证失败的测试用例”；按此指示复跑完整原用例，已向用户说明包含全部原有互动和分享步骤。
- 未验证：原 9 条 suite 整套未复跑；没有另行进入朋友圈列表核验帖子最终可见性。原用例分享流程和返回 App 的断言通过。
- 清理遗留：本轮新增评论 `不错`、点赞及收藏状态未回滚；分享内容未清理。不能将 passed 解释为清理完成。
- 下一步：如需整套结论，单独复跑原 suite；如需回滚本轮数据，确认目标评论 / 互动 / 分享内容后按实际记录清理。
- 本轮只读及完整测试会话都已退出，结束时无 pytest / probe 设备占用；多个历史 Appium 服务未变动。原失败会话查询为 invalid session；Appium 3 会话枚举需 `session_discovery`，没有更改服务器安全配置。

实际验证命令（仓库根目录；基线代码见本节说明）：

```bash
PYTHONPATH=apps/velowind-app/appium VW_APPIUM_RUN_ID=20261010-ios-short-note-unit-final .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_home_feed_helpers.py apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q --tb=short -k 'not validates_video_only_when_media_type_is_video and not android_video_publish_preserves_explicit_source and not forwards_observed_video_progress_signal and not camera_video_publish_does_not_validate'
PYTHONPATH=apps/velowind-app/appium VW_IOS_TARGET=device VW_APPIUM_RUN_ID=20261010-ios-short-note-readonly VW_APPIUM_AUTO_OPEN_REPORT=false .venv/bin/python -m pytest .tmp/appium-ios/short-note-fix/test_browse_readonly.py -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261010-ios-short-note-readonly/allure-results
allure generate .tmp/appium-ios/runs/20261010-ios-short-note-readonly/allure-results --clean -o .tmp/appium-ios/runs/20261010-ios-short-note-readonly/allure-report
git diff --check
```

## 第 2 轮：完整失败用例真机复跑

- 用户再次明确要求验证原失败用例；本轮使用原始 pytest nodeid，执行全部原有步骤及断言。
- 启动前未见其他 pytest / probe 进程；复用 4723 Appium 服务，不结束历史服务器。
- run ID：`20261010-ios-short-note-full`；目录 `.tmp/appium-ios/runs/20261010-ios-short-note-full/`。
- 当前状态：`1 passed`，耗时 74.00 秒；7 个 Allure 步骤全部 passed：准备首页、打开第一篇、浏览、评论、点赞、收藏、朋友圈分享。未修改原测试用例或跳过断言。
- 报告生成成功：`allure-report/`；临时入口 <http://127.0.0.1:51181/>。
- 日志：上述运行目录 `pytest.log`；逐步 PNG 附件在 `allure-results/` 和 HTML 报告中。
- 截图核验：第 6 步详情仍为标题 / 正文 `测试`，新增评论 `不错` 显示 `刚刚`；评论数从 0 到 1，点赞 / 收藏分别为高亮状态且计数为 1。第 7 步返回 App 首页，左上角有微信返回入口。
- 第 6 步截图：`allure-results/f9401aee-4cf5-47b2-a6e8-6689c7269360-attachment.png`；第 7 步截图：`allure-results/a45ac384-821b-43e4-90f2-e7d8011f1a9e-attachment.png`。
- 清理：原用例没有自动回滚评论 / 点赞 / 收藏 / 分享；本轮没有执行删除。Allure 没有 cleanup 结果附件，不能宣称清理成功。
- 本轮结论：原失败用例完整真机通过，修复有效；整套和朋友圈最终帖子可见性未另行验证。

```bash
PYTHONPATH=apps/velowind-app/appium VW_IOS_TARGET=device VW_APPIUM_RUN_ID=20261010-ios-short-note-full VW_APPIUM_AUTO_OPEN_REPORT=false VW_APPIUM_CAPTURE_EACH_STEP=true .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_ios_message_browse.py::test_logged_in_user_can_browse_comment_and_interact_with_note -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261010-ios-short-note-full/allure-results
allure generate .tmp/appium-ios/runs/20261010-ios-short-note-full/allure-results --clean -o .tmp/appium-ios/runs/20261010-ios-short-note-full/allure-report
allure open .tmp/appium-ios/runs/20261010-ios-short-note-full/allure-report --port 0
```
