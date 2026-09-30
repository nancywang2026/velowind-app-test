# 2026-09-21 iOS 笔记详情加载失败

## 范围与当前状态

- 用户要求：修复报告中的 `test_logged_in_user_can_browse_comment_and_interact_with_note`。
- 涉及模块：home_feed.py、message_detail.py。
- 平台：iOS 真机；当前状态：修复完成，目标完整用例真机 1 passed；互动数据未清理。
- 最后核实时间：2026-09-21。
- 历史参考：[iOS P1](2026-09-14-ios-p1.md)：错误叶子节点和祖先可见性需区分；不能吞掉真实失败。

## 失败证据

- 原运行：`20260921-094056-88263`，目录 `.tmp/appium-ios/runs/20260921-094056-88263/allure-report/`。
- 临时 URL：http://127.0.0.1:63845/#suites/b7c906346c289b3cab0da2ebee91532b/4c6f09284dbe2d83/
- `open-first-note` 通过，`browse-note-detail` 失败：`Message detail did not expose all expected fields`。
- 附件：报告 `data/attachments/74357d2ad284ccd4.png` 和 `dbda1abe66950b4c.xml`。
- 截图确认保障车封面下是“加载失败 / 详情加载失败，请稍后再试。”，没有互动栏。
- XML 同时保留首页和活动页的内容，错误文案被解析成标题，底层列表被解析成正文和评论。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：`message_detail_is_visible` 仅凭 `post-detail-page` 壳即可返回真；`open_first_home_message` 在检查错误前就可能返回。
- 已确认：详情解析仅对 Android 限定详情子树，iOS 会混入底层页面内容。
- 尚未确认：原详情请求失败的服务端/网络原因，需现场复核；不能通过换一篇笔记掩盖真实产品故障。

### 修改

- 限定详情子树；显式加载错误直接失败；打开步骤等待详情字段，保留原笔记失败。

### 验证

- 初轮单元：231 passed、5 failed。5 条均为发布流程的既有 mock 问题；将 HEAD 的原 publication 函数载入同一测试环境后，同样 5 failed。日志 `.tmp/appium-ios/note-detail-fix/baseline.log`。
- 真机第 1 轮：只读 probe 调用成功，但字段审计不合格：标题为 `post-detail-page`，评论数误取时间戳 20，未识别短评论。不能算浏览断言通过。证据 `.tmp/appium-ios/note-detail-fix/{probe.log,after.xml,after.png,result.json}`。开始时未发现运行中的 pytest，多个历史 Appium 服务仍在。
- 清理：原用例在发表评论前失败，无本轮新增数据。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 对照截图与 XML | 加载错误与详情字段缺失 | 已确认真实错误页，不能只扩大超时 |

## 遗留项与交接

- 已完成：原报告和源码检查。
- 已完成：限定详情解析范围、加载错误诊断、字段解析回归、真机浏览断言。
- 已完成：用户授权后执行完整目标用例，真机 1 passed，7 个 Allure 步骤全部 passed。不是整套 suite 通过。
- 原报告详情请求失败的服务端/网络原因未确认，本次同一篇笔记恢复正常；保留真实加载错误失败，不跳过到另一篇。
- 当前运行已结束并退出自建会话，无本次 pytest/probe 占用；本次新增评论及互动状态未清理。
- 前两轮仅读取详情；第 3 轮在明确授权后执行完整流程。

## 第 2 轮：字段审计修正

- 新证据：原笔记“一辆骑行保障车内部长什么样?” 本次正常加载，真实评论头为 3；首轮返回 20 来自祖先合并标签中的“20 小时前”。原报告网络/服务端失败原因仍无法追溯。
- 修正：iOS 用详情 StaticText 读取文本，评论数只匹配独立标签；按评论正文、时间、回复结构识别“不错”等短评论。保留选中详情滚动区域中的屏外内容，错误检测单独检查祖先可见性，避免把隐藏错误当作当前失败。
- 无效尝试：只限定子树仍会把 testID 当标题；删除所有屏外节点丢失评论，却仍残留祖先合并标签。已改正，不能以首轮函数返回成功作为验证通过。
- 单元结果：232 passed、5 deselected；排除的是第 1 轮已复核的既有发布 mock 失败，没有把它们计为通过。
- 真机第 2 轮：浏览部分通过，包含原用例对标题、正文、废弃浏览量、评论数和评论内容的全部浏览断言，并额外确认同一笔记标题。返回评论数 3、评论“不错 / 真帅”。
- 证据：`.tmp/appium-ios/note-detail-fix/round2/{before.xml,after.xml,after.png,result.json}`；日志 `.tmp/appium-ios/note-detail-fix/probe-round2.log`。未生成新的完整 Allure suite；这是独立只读 probe。
- 清理：未创建评论、点赞、收藏或朋友圈内容，无本轮新增数据需清理；旧评论未删除。
- 静态检查：`git diff --check` 通过。

实际验证命令（仓库根目录）：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_home_feed_helpers.py apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q --tb=short -k 'not validates_video_only_when_media_type_is_video and not android_video_publish_preserves_explicit_source and not forwards_observed_video_progress_signal and not camera_video_publish_does_not_validate'
PYTHONPATH=apps/velowind-app/appium VW_IOS_TARGET=device VW_APPIUM_RUN_ID=20260921-note-detail-probe-round2 .venv/bin/python .tmp/appium-ios/note-detail-fix/probe.py
```


## 第 3 轮：完整原用例验证

- 用户已明确授权继续完整验证，包括发表评论、点赞、收藏和朋友圈分享。
- 开始前检查：未发现其他 pytest / probe 正在运行，复用 4723 Appium 服务，不结束其他服务。
- 运行 ID：`20260921-note-detail-full`；目录 `.tmp/appium-ios/runs/20260921-note-detail-full/`。
- 状态：1 passed，耗时 141.18 秒；7 个 Allure 子步骤均 passed，无 failed / broken。逐步骤截图已保存；本轮成功步骤附件只有 PNG，无 XML，不能宣称保存了成功步骤 XML。

```bash
PYTHONPATH=apps/velowind-app/appium VW_IOS_TARGET=device VW_APPIUM_RUN_ID=20260921-note-detail-full VW_APPIUM_CAPTURE_EACH_STEP=true .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_ios_message_browse.py::test_logged_in_user_can_browse_comment_and_interact_with_note -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20260921-note-detail-full/allure-results
```

### 第 3 轮结果与证据

- 原用例完整执行，未改断言、未跳过步骤：准备首页、打开第一篇、读取详情、评论、点赞、收藏、朋友圈分享。
- 截图核验：评论区由 3 条增至 4 条，新评论“不错”显示“刚刚”；分享后截图为 App 首页，系统左上角有“微信”返回入口。
- 分享结论边界：原用例的分享流程与返回 App 断言通过；未另行打开微信朋友圈列表验证帖子最终可见性。
- 清理状态：未清理。本用例没有评论/点赞/收藏/朋友圈数据回滚；不能把 passed 解释为数据已删除。
- 日志：`.tmp/appium-ios/runs/20260921-note-detail-full/pytest.log`。
- Allure：`.tmp/appium-ios/runs/20260921-note-detail-full/allure-report/`；原始结果 `allure-results/`。
- 报告生成：`allure generate .tmp/appium-ios/runs/20260921-note-detail-full/allure-results --clean -o .tmp/appium-ios/runs/20260921-note-detail-full/allure-report`，成功。
