# 2026-10-19 真机视频摄像头标识偏移

## 范围与当前状态

- 用户要求：修复自动化脚本，所有 case 通过；当前为测试环境真机。
- 用例：`test_four_home_videos_play_normally`；App 1.3.0 / build 64，iPhone 17，窗口 402 × 874，截图 1206 × 2622。
- 当前状态：47 单元通过；原视频目标在真机整套运行中已 passed，后续用例继续运行；最后核实 2026-10-19。
- 历史参考：[首页视频筛选](2026-09-14-ios-p1.md)、[模拟器筛选](2026-09-16-ios-simulator-video-discovery.md)。当前真机有稳定 card ID，不是旧模拟器缺 ID 的问题。

## 失败证据

- 运行 `20261019-device-test-home-video`，目录 `.tmp/appium-ios/runs/20261019-device-test-home-video/`；无独立临时 URL。
- 登录及首页准备通过；视频扫描前 0–9 页未找到候选。第 4 页肉眼可见多个摄像头图标。
- 证据：`artifacts/home-video-playback-1792395488829260000/feed-page-04.{xml,png}`。
- 卡片 `pst-d90257c8a40c4ec8bbcc27ffb2a026a7` 坐标 (4,407,195,308)，右上摄像头可见。
- 从该卡片按现有算法裁剪 42 × 42 点的区域，原尺寸模板最佳 IoU 为 0.933806，偏移 (57,20)；旧扫描 y 范围 24–64，完全错过最佳位置。

## 第 1 轮：分析、修改与验证

### 已确认原因与修改

- `home_camera_badge.py` 将模板搜索 y 起点由 24 调为 16；保留 x 范围、模板尺寸、0.72 IoU 阈值、空心轮廓判断、视频去重及播放断言。
- 回归 fixture `tests/unit-test/fixtures/home_camera/video-130.png` 来自上述真实截图的卡片角落，只含图标与背景，无账号信息。
- 原有照片、纯色、遮挡与 Android 阴性/阳性样本继续验证。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_home_video_playback.py -q
```

- 单元结果：47 passed，0.87 秒；既有 LibreSSL warning。
- 同一第 4 页离线复验：原代码候选 `[]`，修复后识别 `pst-d90257c8a40c4ec8bbcc27ffb2a026a7`、`pst-df572e08adc44f298b4a5102d5c9d23e` 两个视频。
- 原真机运行已主动中断（311.48 秒、KeyboardInterrupt），driver 正常 DELETE session；不计为通过或完整失败。
- 修复后真机整套运行 `20261019-device-test-full-r1`，首项为原视频目标；`ios-full.yaml` 的所有 test 方法逐一传给 pytest，`--maxfail=0` 收集全部结果。
- 环境：`VW_IOS_TARGET=device`、原真机 UDID、`VW_IOS_NO_RESET=true`、Appium 4785、`VW_API_ENV=test`；没有再显式覆盖 API URL，用实际配置映射到 dev-api。
- 控制台日志 `.tmp/appium-ios/device-test-full-r1.log`；报告及附件 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`。运行结果待补。
- 目标视频实际结果：两个不同视频 `pst-4c0f0274cced43f1a1413b9fb6d4d5f4`、`pst-55845d8d72c04c93af2f4115a22406d7` 均持续播放 PASS；视频步骤 67.9 秒，目标用例 CASE PASSED。整套尚未完成。
- 实际清理：仅浏览，无新增业务数据。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 对实际角落搜索最佳模板位置 | 有 card ID、截图有图标但候选为 0 | 证实是偏移边界；缩放模板未解决，最佳 scale 为原始 1.0 |

## 遗留项与交接

- 复跑目标并核对真实播放结果，之后执行整套；不能以离线候选识别替代实际播放通过。
