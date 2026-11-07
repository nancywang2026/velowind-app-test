# 2026-09-15 Android 首页未找到四个视频

## 范围与当前状态

- 用例：`test_four_home_videos_play_normally`，Android 真机 `4ea581b6`。
- App：1.2.6，versionCode 32，安装更新时间 2026-09-15 14:03:01。
- 当前状态：2026-10-27 第4轮复发1/2，已补受控滚动并在探针中找到2个候选，235项联合单元通过；完整播放复验因真机离线未执行完成。2026-09-20历史真机通过保留，不能代表本轮；整套未验证。
- 历史：iOS 首页视频记录要求摄像头标识及四个不同视频，仍保留该要求；原 Android 初始化问题另见 `2026-09-15-android-hidden-api.md`。

## 失败证据

- run `20260915-android-home-videos-r3`，`.tmp/appium-android/runs/20260915-android-home-videos-r3/allure-results`。
- `02-verify-four-home-videos`，25.5 秒后失败：只找到 0/4 个不同视频，不能标记通过。
- 截图 `798807ea-28ea-42e0-8401-764b1cc0a640-attachment.png`：推荐页已到底，末屏没有摄像头图标。
- XML `d6bacb31-3b92-4f5d-ae6c-ebf932725849-attachment.xml`：5 个 note-card ID，0 个 video-badge ID。说明卡片定位 ID 存在，不是全部 testID 缺失。

## 第 1 轮分析与验证

- 已确认：会话及首页准备通过，识别结果为 0；视频未打开，尚未执行实际播放断言。
- 未确认：全部推荐数据是否没有视频，或早期屏幕存在未识别标识。只有末屏截图，不能推断整份列表均为图片。
- 未修改视频选择或播放断言，未用图片替代视频，未制造通过结果。
- 命令详见关联初始化记录，本轮 1 failed，79.80 秒。
- 清理：无新增业务数据；单元/静态验证：本问题没有代码改动，未新增测试。

## 可复用方法与无效尝试

- 初始化成功不代表视频用例通过；“未找到视频”与“打开视频后播放失败”须分开记录。

## 遗留项与交接

- 待确认测试环境首页是否有至少四个带视频标识的笔记，并采集前几屏截图/XML区分数据不足与识别问题。
- 用例未通过，整套未验证；本轮 pytest 已退出。

## 第 2 轮：2026-09-20 真机 0/2 报告复查

### 失败证据与分析

- 用户反馈 Android 首页有视频，报告入口 `http://127.0.0.1:60131/#suites/e2df1617c526fa8fd9b264b94f1409a1/d41c8caadaf5816d/`。
- 报告目录：`.tmp/appium-android/runs/20260920-130821-36527/allure-report/`；用例 `test_four_home_videos_play_normally`，`02-verify-2-home-videos` 失败，37.340 秒，结果 0/2。
- 报告设备为 Android physical、UDID `YHK7EERSGAPZX87X`，Appium 4725；本轮 `adb devices -l` 也确认该真机连接，同时有模拟器，不能把此次失败归为跑错模拟器。
- `data/attachments/4c89023d1d189bff.txt` 记录 page 0–20 全部 `card_ids=True, badge_ids=False, candidates=[]`。
- 首屏 `data/attachments/89e61e8813195727.xml` 存在卡片“一辆骑行保障车内部长什么样?”、“千岛湖东北环湖骑行”等，但无视频 badge ID。
- 已确认：`visible_home_videos` 依赖精确 `post-home-feed-note-video-badge-*` 节点；无标识时需要截图才能启动摄像头图标识别。`verify_four_home_videos` 第 246–247 行仅为 iOS 获取截图，Android 传入 None。因此当前 Android 报告中缺失 badge 的视频无法被识别。
- 未确认：安装包为何不暴露 badge（应用未设置或 Android 可访问性树合并等原因尚未核实）；本次报告没有逐屏 Android 截图，不能从 XML 单独确认哪些卡片是视频。

### 修改与验证

- 本轮为原因排查，仅追加记录，未修改测试逻辑。
- 执行：读取报告 JSON、逐屏筛选诊断及首屏 XML，对照 `home_video_playback.py`，执行 `adb devices -l`，检查 Appium / pytest 进程。
- 当前未发现运行中 pytest；已有多个 Appium 服务，本轮未新建或替换任何设备会话。
- 用例断言：原报告 failed，0/2；播放阶段未执行。单元测试、修复后真机验证、整套：均未执行。
- 清理：不涉及，无新增业务数据。

### 当前状态与下一步

- 已定位 Android 视频候选识别缺口，不能将 0/2 解读为首页没有视频。
- 下一步：采集真机首屏截图与 XML 核对图标及像素密度，补齐 Android 候选识别并增加真实样本回归，再执行目标真机用例。不能直接假定 iOS 的固定裁剪尺寸适用于 Android。

## 第 3 轮：2026-09-20 Android 截图识别修复与真机验证

- 首屏截图 `.tmp/android-video-fix/home.png` 确认两个视频摄像头图标；设备物理密度 520 dpi（3.25 px/dp）。
- 修改 `home_video_playback.py`：Android 启用截图候选识别和逐屏截图留证；通过 Appium display density 将图标裁剪的 dp 转换为 Android 像素坐标，保留 iOS 默认倍率和原播放断言。
- 从实际首屏提取两个视频、一个图片角标区域，新增真实 Android 截图回归，校验识别与点击位置。
- 单元验证命令：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_home_video_playback.py -q`；46 passed，0.75 秒。
- 真机验证前无运行中 pytest，4725 日志确认前一个 session 已于 13:09:25 删除；未终止其他服务。真机目标用例即将执行，结果待追加。

### 第 3 轮真机结果

- 真机：`YHK7EERSGAPZX87X`，App 1.2.6 / versionCode 35。
- 命令：

```bash
VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_ANDROID_UDID=YHK7EERSGAPZX87X VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 VW_APPIUM_AUTO_OPEN_REPORT=0 VW_APPIUM_RUN_ID=20260920-android-video-density-fix VW_HOME_VIDEO_COUNT=2 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_home_video_playback.py -q -s --alluredir=.tmp/appium-android/runs/20260920-android-video-density-fix/allure-results
```

- 结果：**1 passed，71.41 秒**；视频步骤 47.7 秒。
- 两个不同视频 `pst-5bc104cfbd094fe49a33c7c78a3482dd`、`pst-002a17a151604383ac1c0c674a0b4c45` 均识别成功并通过持续画面变化播放断言。
- 报告目录：`.tmp/appium-android/runs/20260920-android-video-density-fix/allure-report/`；原始结果为同级 `allure-results/`；运行日志 `.tmp/android-video-fix/pytest.log`。
- `git diff --check` 通过。现有 urllib3 / LibreSSL 警告不影响本轮结果。
- 清理：无发布或新增业务数据，无业务数据清理需求；目标用例结束，fixture 完成会话释放。
- 本轮无失败修改尝试；旧失败报告和未暴露 badge 的事实保留。
- 已完成：Android 密度适配、截图识别、真实样本回归、目标真机播放验证。未验证：整套、其他 Android 密度设备及 iOS 真机回归；原 iOS 离线回归包含在 46 项通过结果中。

## 第 4 轮：2026-10-27 登录准备修复后出现1/2

- 用户原报告55083为环境登录 setup 失败，见 [Android 环境登录准备](2026-10-27-android-environment-login.md)，不是本条历史0/2的直接复发。补齐登录兼容后 run `20261027-android-environment-login-r3` 到达真实视频步骤。
- 真机 YHK7EERSGAPZX87X / Android16 / 实际App1.2.8(code39)，prod凭据 App 登录成功；r3 **1 failed / 24 deselected / 152.04秒**。首个视频 `pst-e6bba5694f2f4c52830634bb86b81947` 播放passed，随后21屏扫描没有找到第二个不同视频，完整断言失败。
- 报告/原始结果 `.tmp/appium-android/runs/20261027-android-environment-login-r3/{allure-report,allure-results}/`；逐屏PNG/XML位于该run `artifacts/home-video-playback-*/feed-page-*`，诊断附件 `f8ada3bb-02d6-4029-ad69-9717c62e5e6a-attachment.txt`。
- 已确认逐屏候选仅page0有1个，其他屏空；最后一屏显示已到底。不能从最后图片屏断言全部数据仅1个视频。
- 新观察：前几屏每屏6–8张卡片，page1与前屏重叠2张，page2–7与前屏均0重叠。Android compatibility将 mobile:swipe映射为未指定speed的 swipeGesture，可能惯性跨过部分卡片角标；这是待验证推测，尚未修改或认定是原因。
- 设备无其他pytest，启动只读受控滚动探针：同一登录环境/首页，用scrollGesture小步慢速滚动，每屏截图/XML及候选留证，目录 `.tmp/appium-android/runs/20261027-video-scroll-investigation/`。不新增业务数据，不降低目标数量，不用探针代替最终播放断言。
- 下一步：比较慢速连续扫描是否能找到原规则识别的第二个视频；如果不能，继续区分数据与识别问题。完整原目标目前仍失败，未清理事项不涉及新增。

### 第 4 轮滚动探针首次无效

- 首探针调用 ensure_read_session_on_home 后未显式选择笔记Tab，重启App实际默认活动Tab；截图确认扫描的是活动列表，12屏无笔记卡片ID，不能用于比较视频数量/手势覆盖。此探针未提交业务数据，正常quit。
- 重做探针目录 `20261027-video-scroll-investigation-r2`，显式点击 bottom-nav-home，并断言真实笔记 feed 的 `post-home-feed-category-scroll` 存在后才扫描。前次无效探针保留，未据此认定数据不足。

### 第 4 轮对照证据与修改

- 修正后的只读探针：page0找到原视频；小步滚动后的page3找到第二个不同视频 `pst-c4a25e7b6d104f409fabdd2f67fa6d7b`。使用原 visible_home_videos / 摄像头识别规则，未改候选条件。原r3的21屏XML中完全没有这个postId，支持原手势跳过卡片的判断，不能归因为生产首页仅1个视频。
- 对照参数：scrollGesture，扫描区域top=17%窗口高度/height=70%，percent=.55，speed=1000像素/秒；每页保留截图/XML。探针未打开/播放第二个视频，只证实候选可发现；完整播放仍需用例验证。
- 修改 `home_video_playback.py::verify_four_home_videos`：仅 Android 扫描使用该受控 scrollGesture；iOS原手势保留。全局 swipe compatibility不变，避免影响其他模块。
- 新增 Android 完整扫描流程单元：两个不同页面视频必须分别播放检查，使用重叠scroll而非默认fling；原不同ID、图片排除、数量、错误及播放阈值断言保留。
- 本轮联合单元及完整目标真机待补；不将候选探针当成播放通过。

### 第 4 轮最终复验进度

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_environment_login.py apps/velowind-app/appium/tests/unit-test/test_auth.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py apps/velowind-app/appium/tests/unit-test/test_home_video_playback.py -q --tb=short
```

- **235 passed / 18.64 秒**，`git diff --check` 通过；既有 LibreSSL warning。覆盖登录、会话、视频候选和播放阈值。
- 探针及前序 pytest 已结束，按 [Android登录记录](2026-10-27-android-environment-login.md) 第1轮完整suite定向命令启动 `20261027-android-environment-login-r4`，run/artifact ID对应改r4；不设置 VW_HOME_VIDEO_COUNT，不降低默认2个目标。
- 真实完整用例运行中，未提前计通过；整套、其他设备未复验。没有新增业务数据，无发布/删除清理步骤。

### 第 4 轮完整复验被设备离线阻断

- `20261027-android-environment-login-r4` 在 pnpm preflight 即失败：`Configured Android device is not online: YHK7EERSGAPZX87X`，没有进入 pytest、没有创建新 Appium 会话，不能计为真机失败断言或通过。
- 此前已完成235项单元、慢速连续扫描发现2个不同视频；修改后完整播放/目标用例尚未验证。原r3只有1个视频播放通过，不能将候选探针补为第2个播放结果。
- 当前阻塞为物理设备离线，待设备恢复后用同命令新run复验；不结束任何既有Appium/adb服务。无新增业务数据或待删除目标。
