# 2026-09-15 Android 首页未找到四个视频

## 范围与当前状态

- 用例：`test_four_home_videos_play_normally`，Android 真机 `4ea581b6`。
- App：1.2.6，versionCode 32，安装更新时间 2026-09-15 14:03:01。
- 当前状态：2026-09-20 第 3 轮 Android 真机目标用例通过，两个不同视频播放通过；整套未验证。第 1 轮失败事实保留如下。
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
