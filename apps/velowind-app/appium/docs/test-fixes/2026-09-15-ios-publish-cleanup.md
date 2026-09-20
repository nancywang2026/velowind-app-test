# 2026-09-15 发布详情误选、换行标题与自动清理

## 范围与当前状态

用户要求同步修复清理模块，并提醒标题可能换行；随后反馈图片发布用例再次失败。本记录保存连续尝试，包括未成功的方法。

- 平台：iOS 真机，iPhone，系统 26.2.1，App bundle `com.velowind.rider`；本次没有核实 App 构建版本。
- 发布用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`、`test_user_can_publish_xiaodai_video_note_for_review[xiaodai-0424]`、`test_user_can_publish_video_record_note_for_review[publish-note-video-camera]`。
- 当前已确认：`20260915-101707-55481` 三个发布用例均通过，但三条清理均 pending。后续整套运行 `20260915-102919-66991` 的已落盘结果中，图片和相册视频已各有 `publish-note-cleanup-result`，deleted 为对应标题，skipped 为空。
- 上述后续结果是文档补录时读取的部分结果，不代表整套完成，也不代表现场录制视频清理已成功。
- 补录时间：2026-09-15，Asia/Shanghai。参考 [前一轮记录](2026-09-14-ios-p1.md)。

## 问题一：图片用例误入视频详情

### 第 1 轮：发现实际页面不是图片笔记

- 运行：`20260915-094150-36263`。
- 报错：`Unable to locate the published note detail image for pixel validation`。
- 证据：失败截图是自行车视频，而用例期待长白山图片；失败发生在媒体校验阶段，还未进入清理。
- 分析：应先排查目标笔记定位，不能仅增加图片等待时间。
- 修改：iOS 未找到实际标题矩形时，不再退回点击包含标题的整页汇总 XPath；标题比较忽略空白和换行。
- 结果：下一轮图片用例通过，但这一修改没有覆盖所有“进入任意详情即可返回成功”的路径，后面仍复发。

### 第 2 轮：再次复发，补齐详情身份核验

- 用户报告：[失败详情](http://127.0.0.1:58544/#suites/a315921332822b24a92de7455c3da80b/28bb82532e91df39/)。
- 运行：`20260915-100832-51183`。
- XML 证据：`post-detail-page` 的标签属于 `Velowind｜解锁-0d8bb7db`；截图显示视频播放画面，不是图片用例的目标笔记。
- 证据文件：`.tmp/appium-ios/runs/20260915-100832-51183/allure-report/data/attachments/cf2b395f0794b18f.png` 和同目录 `e476f224fc230261.xml`。
- 已确认缺陷：`_open_published_note_detail_from_my_notes` 把 `message_detail_is_visible` 当成成功条件，没有检查目标标题；图片校验已在详情页时也可能跳过目标定位。
- 推测风险：列表异步重排会让旧坐标落到其他卡片。仅凭现场截图不能证明每次误选都由重排触发，因此同时修复点击身份和进入后的验证。

修改文件：[message_detail.py](../../velowind_appium/modules/message_detail.py)。

1. iOS 卡片按 `post-home-feed-note-card-*` 的 accessibility ID 点击，避免沿用旧矩形中心。
2. 标题候选局限到我的笔记列表（存在该容器时），排除隐藏祖先下的节点和整页汇总容器。
3. 新增 `_ios_published_detail_title` / `_ios_published_detail_matches_title`，核验详情标题；误入其他详情时返回列表继续找。
4. 图片、视频内容校验前均执行目标详情核验；竖屏视频下方不可见的标题文本可以用于识别详情身份，删除前仍另做可见标题确认。
5. 成功识别目标详情后记录实际持久化标题，供后续精确清理使用。

验证：

- 单元回归先后记录 206 passed、232 passed；另补错误详情返回后的状态流测试并通过。新增文件 [test_ios_note_cleanup.py](../../tests/unit-test/test_ios_note_cleanup.py) 当时合计 12 passed。这些是不同阶段的检查结果，不能简单相加成一轮测试数量。
- 真机 `20260915-101707-55481`：三个发布用例均通过，663.23 秒；图片详情校验与相册视频内容校验通过。
- 报告目录：`.tmp/appium-ios/runs/20260915-101707-55481/allure-report/`；当时入口：[Allure](http://127.0.0.1:60905/)。

## 问题二：标题换行、截断与自动清理

### 第 1 轮：合并卡片与换行标题

- 背景：历史整套 14 passed，三个发布用例却都留下 `cleanup-pending`。原清理仍依赖精确 StaticText，无法覆盖 iOS 合并卡片。
- 修改：[cleanup.py](../../velowind_appium/cleanup.py) 增加 iOS 精确笔记清理分支，解析实际卡片标题；匹配时移除空白和换行，避免中文标题中间换行产生额外空格。
- 删除流程：匹配卡片 → 打开详情核对标题 → 更多 / 删除 / 确认 → 返回列表后检查选中笔记 ID 消失。另一张同名卡片仍存在不应导致错误判定。
- 单元覆盖：换行、相似但不相同的标题、隐藏卡片、错误详情、删除后原卡仍在。
- 真机局部结果：使用已存在测试数据，图片笔记返回 `deleted=[实际标题]`。

### 第 2 轮：竖屏视频遮挡标题

- 证据：`Velowind｜解锁-445ab7dc` 的详情标题 StaticText 位于 y=799，XML 标记 visible=false；因此仅等待可见标题一直不能进入删除。
- 修改：进入详情但标题尚不可见时，上滑显示标题，再核对后删除。
- 真机局部结果：该视频返回 deleted，skipped 为空。
- 限制：这证明已有测试笔记的局部 UI 删除可用，不等于发布后导航与自动清理整条链路已经通过。

### 第 3 轮：输入标题和持久化标题不同

- 请求标题：`测试 - 长白山真的有种让人瞬间安静下来的魔力`。
- 实际详情标题：`测试 - 长白山真的有种让人瞬间安静下来`。
- 第一次方法：输入后立即读取输入框 value，保存 `_ios_note_submitted_title`；公共清理读取这个映射。
- 无效证据：`20260915-095238-40858` 的图片用例虽然通过，pending 附件仍是未截断的请求标题。不能把“已添加读取代码”当成真实捕获成功。
- 后续修改：提交前读取稳定表单值；目标详情核验成功后再次读取持久化标题。
- 结果：`20260915-101707-55481` 的清理附件已使用实际截断标题，但仍 pending，说明还存在列表进入 / 加载问题。

### 第 4 轮：列表加载等待

- 现象：清理得到 deleted=[]、skipped=[]；此前局部验证多读取一次列表后可删除。
- 分析：进入“我的笔记”返回时，卡片可能尚未异步加载；立即判定没有目标并退出页面会错过卡片。此处最初是待验证的原因，不是仅凭空结果就确定的根因。
- 修改：`_cleanup_exact_ios_note` 在当前列表内等待精确目标卡片，最多 8 秒，避免立即返回空结果。
- 验证：12 项清理相关单元检查通过。独立真机验证随后发生会话失效，见问题四，不能将该次尝试算成功。
- 后续可核实结果：`20260915-102919-66991` 的图片和相册视频发布用例已记录实际删除成功。文档补录时只依据已落盘附件记录，其他用例仍需等待最终报告。

### 清理结果记录方式

[shared_publish_note.py](../../tests/shared_publish_note.py) 在成功时写 `publish-note-cleanup-result`，未完成仍写 `publish-note-cleanup-pending`。当前逻辑允许发布通过但清理 pending，后续报告必须分别检查。

文档补录时，工作区另出现了 [note_api_cleanup.py](../../velowind_appium/note_api_cleanup.py) 及 `VW_NOTE_CLEANUP_MODE=ui|api` 分支。该变更不属于上面已描述的 UI 修复验证轮次；不能把本篇 UI 结果外推成 API 清理真机验证结果。后续使用时需记录模式、实际调用结果和对应报告。

## 问题三：视频采样时实际缓冲

- 运行：`20260915-095238-40858`，图片通过，相册视频失败。
- 报错：`Published note video screenshot 4 was still loading or blank after 10 attempts`。
- 证据：失败截图可见“正在缓冲视频...”。视频画面存在但播放器仍在缓冲，不能当成持续正常播放。
- 截图：`.tmp/appium-ios/runs/20260915-095238-40858/allure-results/ad987763-f697-4def-be7c-3e34ad26a135-attachment.png`。
- 处理：保留这次失败，不放宽断言掩盖缓冲。后续 `20260915-101707-55481` 的视频内容校验通过，不据此宣称应用缓冲问题已被代码修复。

## 问题四：独立验证与整套测试竞争会话

- 独立清理验证出现 `InvalidSessionIdException: A session is either terminated or not started`。
- 同时通过进程列表发现另一轮 `ios-p1.yaml` 已启动，运行目录为 `20260915-102919-66991`。会话替换是高度相关原因，独立验证未完成。
- 处理：停止新增真机会话，通过已运行测试的报告观察结果，不结束另一轮测试。
- 下次先查进程，再决定是否新建 driver；不要同时启动独立调试脚本与整套真机测试。

## 本次使用的验证方式

临时 suite `/tmp/ios-cleanup-publish-suite.yaml` 内容如下；文件不保证长期存在，需复用时可按此内容重建：

```yaml
tests:
  - message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]
  - message/test_ios_xiaodai_publish_video.py::test_user_can_publish_xiaodai_video_note_for_review[xiaodai-0424]
  - message/test_ios_publish_video_record_note.py::test_user_can_publish_video_record_note_for_review[publish-note-video-camera]
pytest_args:
  - --maxfail=1
```

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.run_ios_tests --suite /tmp/ios-cleanup-publish-suite.yaml
PYTHONPATH=apps/velowind-app/appium .venv/bin/pytest -q apps/velowind-app/appium/tests/unit-test/test_ios_note_cleanup.py apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py apps/velowind-app/appium/tests/unit-test/test_cleanup_helpers.py apps/velowind-app/appium/tests/unit-test/test_cleanup_report.py
git diff --check
```

避免对整个 tests 目录仅用 `-k` 过滤后收集：本会话曾碰到无关单元模块的 `regression` 导入错误。针对目标路径运行，或使用 suite 中的精确 selector。

## 报告时间线

| run ID | 实际结果 | 清理 / 限制 |
| --- | --- | --- |
| `20260915-094150-36263` | 图片失败：误入视频，找不到图片 | 未进入清理 |
| `20260915-095238-40858` | 图片 passed；相册视频因缓冲 failed | 图片 cleanup-pending |
| `20260915-100832-51183` | 已落盘 1 passed、1 failed；图片再次误入视频 | 不能称为整套通过 |
| `20260915-101707-55481` | 三个发布用例 passed | 三条 cleanup-pending，彼时删除仍未完成 |
| `20260915-102919-66991` | 补录时图片与相册视频用例已 passed | 两例均有 cleanup-result；不是最终整套结论 |

各运行证据位于仓库根目录 `.tmp/appium-ios/runs/<run-id>/`。

## 交接与下次修复入口

1. 如果再报“找不到图片”，先读详情实际标题和媒体类型，确认是否误入其他笔记，再考虑图片定位器或等待时间。
2. 长标题必须区分请求文本、输入框值、持久化标题和视觉换行；精确清理以确认后的实际标题为准。
3. 不要恢复“任意详情可见即成功”、整页 contains XPath 点击或忽略祖先可见性的旧逻辑。
4. 补查 `20260915-102919-66991` 的最终结果，尤其现场录制视频清理和整套状态；新增结论应追加在本篇或后续记录，不改写之前的 pending。
5. 新的 API 清理分支需要单独记录验证过程，本篇没有提供其真机已通过结论。
