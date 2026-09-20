# 2026-09-16 iOS 模拟器首页视频筛选失败

## 范围与当前状态

- 用例：`test_four_home_videos_play_normally`。
- 当前状态：明确指定真机后目标用例 1 passed（四个不同视频均通过）；已补充逐屏诊断。旧模拟器包问题未修复，整套未验证。
- 原报告配置：iOS simulator，UDID `6C7DEC8B-93A0-447A-834E-180CF29F0C56`。
- 当前只读设备清单：iPhone 17 Pro Max / iOS 26.5；当前安装的 `com.velowind.rider` build 34。当前安装信息不能证明运行时版本。
- 历史参考：[iOS 视频标识识别](2026-09-14-ios-p1.md)、[Android 候选不足](2026-09-15-android-video-candidates.md)。历史成功不能推广到当前模拟器包。

## 失败证据

- run：`20260916-093314-83984`。
- 报告目录：`.tmp/appium-ios/runs/20260916-093314-83984/allure-report/`。
- 临时入口：<http://127.0.0.1:61954/#suites/e2df1617c526fa8fd9b264b94f1409a1/654729167c45f78c/>。
- 失败步骤：`02-verify-four-home-videos`，81.638 秒。
- 报错：`视频播放验证未完成：只找到 0/4 个不同视频，不能标记通过`。
- 附件位于报告 `data/attachments/`：截图 `e77991a55076367c.png`；XML `7bca380236ba5b8a.xml`。
- 截图是推荐列表，末屏未见摄像头标识；XML 窗口为 440 × 956。

## 第 1 轮：分析与离线验证

### 已确认

- 首页准备通过；没有进入任何视频检查子步骤，播放断言尚未执行。
- 末屏 XML 保留 `post-home-feed-pull-viewport`、`post-home-feed-pull-content`、`post-home-feed-category-pager`。
- 末屏 XML 没有 `post-home-feed-note-card-*`、`post-home-feed-note-video-badge-*`；也没有名称包含 camera/video/摄像/视频的节点。
- `visible_home_videos` 的显式标识路径依赖 video-badge ID；截图模板路径依赖 note-card ID 计算封面角落。当前末屏不能建立任何截图候选区域。
- 使用原附件离线调用 `visible_home_videos(source, {'width': 440, 'height': 956}, screenshot_png)`，结果为 `[]`。

### 未确认

- 缺少卡片标识是否覆盖前面全部页面，是否由构建版本或可访问性结构变化造成。
- 推荐列表是否具备至少四个视频；滚动过程是否覆盖了足够数据。
- 视频播放功能是否正常。最后一屏不能证明全部推荐数据均为图片。

### 修改与验证边界

- 仅新增分析记录及索引，未改选择器、播放断言或 App。
- 离线命令环境：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python`，从原 XML/PNG 调用上述函数。
- 单元测试：未运行（无代码改动）。
- 模拟器复跑：未执行；真机：未验证；整套：未验证。
- 清理：本轮只读分析，无新增业务数据。
- 进程检查发现多个 Appium 服务和模拟器 WebDriverAgent，未发现 pytest；未创建或替换设备会话，未结束其他进程。

## 可复用方法与无效尝试

- 先检查候选卡片 ID 是否存在，再讨论摄像头模板阈值。没有候选区域时调节模板阈值无济于事；本轮未进行此类修改。
- 不将“0 个候选”解释成视频播放失败，不以降低四个不同视频的要求解决问题。

## 遗留项与交接

- 下一步采集当前包首页前几屏截图/XML，逐屏记录卡片 ID、视频标识和滚动前后变化，确认实际视频卡片结构。
- 如果视频卡片不暴露稳定标识，应在 App 源码恢复标识或基于现场结构设计可靠定位；本工作区 `apps/velowind-app` 下只有 Appium 工程，没有对应 App 页面源码。
- 定位修复后再执行四个不同视频的播放校验；目前不能标记用例已修复或通过。

## 第 2 轮：核对安装包，改用真机验证并补充诊断

- 用户明确要求修复并真机验证；检查无其他 pytest，采集会话结束后再启动目标用例，未替换他人会话。
- 模拟器当前安装包 Info.plist 确认是 **1.2.4 / build 34**；其 `main.jsbundle` 没有 `post-home-feed-note-video-badge-` 或 `post-detail-video-surface` 字符串。不能仅凭缺少字符串断言整个版本完全不支持视频。
- 真机 `00008150-0006799C2693401C`，iOS 26.2.1，当前 App **1.2.6 / build 53**（devicectl apps 查询）。
- 新证据：`.tmp/home-video-investigation/simulator/page-{0..3}.{xml,png}` 均无卡片 ID、无识别到的视频；真机 `.tmp/home-video-investigation/device/page-{0..5}.{xml,png}` 均有卡片 ID，共发现充足视频候选。
- 原模拟器与当前真机的包版本及页面结构不同；不能用真机通过宣称旧模拟器包已修复。
- 中间尝试：实现过无 ID 卡片的封面/文本结构回退，但模拟器四屏仍无摄像头候选，无法证明回退有效，已撤回。没有保留未经现场证据支持的识别规则，也没有降低视频数或播放断言。
- 保留修改：`home_video_playback.py` 每个扫描页保存 XML、iOS 截图，并附逐屏 card/badge ID 存在性与候选 ID；解决原报告只有末屏、无法追溯筛选过程的诊断缺口。
- 单元验证：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_home_video_playback.py -q`，**41 passed**。
- 目标真机运行：`20260916-home-videos-device-fix`，**1 passed，153.20 秒**；播放步骤 115.0 秒。Allure 两个顶层步骤及四个视频子步骤全部 passed。

```bash
VW_IOS_TARGET=device VW_IOS_UDID=00008150-0006799C2693401C VW_IOS_NO_RESET=true VW_IOS_SHOW_XCODE_LOG=false VW_APPIUM_RUN_ID=20260916-home-videos-device-fix VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20260916-home-videos-device-fix/artifacts VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_home_video_playback.py -q -s --alluredir=.tmp/appium-ios/runs/20260916-home-videos-device-fix/allure-results
```

### 最终验证与交接

- 真机正常播放的四个不同 ID：`pst-4a24613bac144cd8986185f18b66c112`、`pst-fe54f428242b4dd4b27ca3653fa70b4e`、`pst-62c86b5b6a124398bb4b8593907500d2`、`pst-99ae6868d7ff47e1aff3119360bf7a91`。
- 两个扫描页均有 card ID、无独立 badge ID，截图摄像头模板识别成功；逐屏 XML/PNG 及诊断附件已在真实运行中生成。
- 报告：`.tmp/appium-ios/runs/20260916-home-videos-device-fix/allure-report/`；结果：同运行目录的 `allure-results/`。
- `git diff --check` 通过；设备会话和 pytest 已正常结束。
- 清理：仅浏览，无新增笔记、评论或其他待清理业务数据。
- 本轮解决的是明确使用匹配的真机环境完成验证，并补充筛选过程证据；未修改选择/播放断言。没有证明旧模拟器包可通过，模拟器需要匹配版本的构建后另行验证。
- 范围仅此目标用例，整套未验证。

## 第 3 轮：再次运行仍选择模拟器

- 用户报告：<http://127.0.0.1:64961/#suites/e2df1617c526fa8fd9b264b94f1409a1/ef34625637d03dd0/>。
- run：`20260916-095254-92849`，报告在 `.tmp/appium-ios/runs/20260916-095254-92849/allure-report/`。
- 报告配置明确为 `target='simulator'`、UDID `6C7DEC8B-93A0-447A-834E-180CF29F0C56`、server `http://127.0.0.1:4725`，不是上一轮通过的真机配置。
- 新增诊断附件 `1dfee1f4e1034c1c.txt` 显示 page 0–20 全部 `card_ids=False, badge_ids=False, candidates=[]`。因此此次可确认全部扫描页均未获得定位标识，而不只是末屏缺失。
- 结果仍为 0/4，未执行播放校验。上一轮仅临时指定真机运行并补诊断，未修复模拟器兼容，也未修改用户的重新运行入口。
- 尚未确定重跑入口在哪里设置了 simulator/4725；不推断是用户手动选择或某个脚本覆盖。当前未再次运行设备测试，无新增业务数据。
