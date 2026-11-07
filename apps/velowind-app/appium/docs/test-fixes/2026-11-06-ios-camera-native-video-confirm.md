# 2026-11-06 iOS 录制视频缺少系统确认步骤

## 范围与当前状态

- 用户要求：继续修复 52039 报告中的测试用例。
- 用例：`test_user_can_publish_video_record_note_for_review[publish-note-video-camera]`。
- 模块：`photo_picker.py` 拍摄、系统确认、App 预览时长校验。
- 平台：iOS 真机，iOS 26.2.1，窗口 402×874；App 版本本轮未核实；生产环境，API 清理。
- 当前状态：已补系统确认分支及回归用例；单元 96 passed；真机创建会话因设备离线失败，完整流程及清理未验证。
- 最后核实时间：2026-11-06（Asia/Shanghai）。
- 历史参考：[Android 相机权限](2026-09-20-android-camera-permission.md)、[媒体验证与会话冲突](2026-09-15-ios-publish-cleanup.md)。本次未出现 Android 权限弹窗，不能套用该原因；继续遵守真机单会话约束。

## 失败证据

- run：`20261106-163358-33701`，目录 `.tmp/appium-ios/runs/20261106-163358-33701/allure-report/`。
- URL：`http://127.0.0.1:52039/#suites/8a1699b7f514293d5bbf66b4d6472144/d09ced5b13e0a22f/`。
- 失败步骤：`02-publish-note-for-review-publish-note-video-camera`；报错：`Video camera opened but recording could not be completed.`。
- 附件：`data/attachments/6641d5811735a7eb.png`、`8d5c0e63c5cbe776.xml`。
- 截图停在系统录制结果页，底部为“重拍／播放／使用视频”；XML 对应按钮 name 为 `Cancel`、`Playback`、`Done`，label 为中文。滑动条 value 为 `0:0:0.00，共0:0:0.00`，不能用来证明已录制有效时长。
- 预期：接受系统视频后进入 App 预览，再读取正数实际时长并确认；实际：脚本仅等包含“预览视频”的 App 页面，跳过系统确认导致超时。
- 本次原失败尚未发布，无已发布笔记需要清理；本地临时媒体未验证清理。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：`_record_video_from_camera` 停止录制后仅等待 `_camera_video_preview_visible`，该函数只认“预览视频”；失败 XML 没有此文字，有可见的系统 `Playback` 与 `Done`。
- 推测：补系统确认可解除当前超时；原录制是否产生有效视频需真机读取 App 预览时长确认，不能由系统确认页推断。

### 修改

- `photo_picker.py`：iOS 停止后兼容系统与 App 两级预览；仅在可见 `Playback` 与 `Done` 同时存在时点击可见的原生 Done 按钮，随后仍等待 App 预览、要求正数时长并执行 App 确认。
- `test_photo_picker_helpers.py`：增加系统中英文标识、隐藏节点、非系统预览、正数／缺失／零时长、系统确认未跳转的回归。
- 不修改 Android 录制路径、录制时长配置、发布断言及清理策略。

### 验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=false PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py apps/velowind-app/appium/tests/unit-test/test_android_camera_cleanup.py -q --tb=short
```

- 第一轮单元：95 passed、1 failed，39.62 秒；run `20261106-180430-38045`。失败为 `test_android_cleanup_uses_title_accepted_by_native_input`，其预期 UI 模式采用截断标题，但仓库默认 API 模式采用完整标题。该测试不调用本次修改的录制路径，未修改清理行为。
- 显式 `VW_NOTE_CLEANUP_MODE=ui` 重跑以上命令：96 passed，39.53 秒；run `20261106-225545-40477`；既有 LibreSSL warning。保留首次失败，不将首次计为全通过。
- 原 XML 离线回放：旧 `预览视频` 标记 false，新系统预览识别 true；仅证明失败页面可被新分支识别，不能替代真机点击验证。
- 真机：启动前进程检查无 pytest；早先 `xctrace` 显示设备在线，Appium 4723 可用。run `20261106-ios-camera-native-confirm-r1` 在 driver setup 报 `Unknown device or simulator UDID: '00008150-0006799C2693401C'`，pytest **1 error**，Allure `broken`，0 个业务步骤。随后重新执行 `xcrun xctrace list devices` 确认该设备在 Devices Offline。未切换到其他设备，未终止既有 Appium。
- 清理：未执行；原失败未发布，本轮 setup 未完成，未新增已发布笔记。
- 静态：本次四个修改文件的 `git diff --check` 通过。
- 进程：开始时无 pytest；保留既有 Appium 4723、WDA xcodebuild 与 Allure 服务，没有结束他人进程。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 对照 name 与 label，辨别系统预览和 App 预览 | iOS 原生拍摄流程 | 本次 name 为英文、label 为中文，系统确认是独立一步 |
| 直接把系统 Done 当最终确认或跳过时长校验 | 本次不采用 | 系统滑动条为零，必须进入 App 读取有效时长 |

## 遗留项与交接

- 已完成：原失败截图与 XML 核实、最小确认分支及回归用例。
- 本轮结论：已修补确认流程缺口，单元及原 XML 回放通过；由于设备离线，不能称真机用例修复完成。
- 未完成：原真机用例完整复跑、实际清理核验；整套未验证。
- 产物：`.tmp/appium-ios/runs/20261106-ios-camera-native-confirm-r1/pytest.log`、`allure-results/`、`allure-report/`，保留 setup 阻断结果。
- 下一步：重新连接并解锁原 iPhone；再次检查无其他测试占用后，用新的 run ID 重跑以下命令，独立核对实际时长、发布断言、`publish-note-cleanup-result` / `publish-note-cleanup-pending`。

```bash
VW_API_ENV=prod VW_NOTE_CLEANUP_MODE=api VW_IOS_NO_RESET=true VW_APPIUM_AUTO_OPEN_REPORT=false VW_APPIUM_RUN_ID=20261106-ios-camera-native-confirm-r1 VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261106-ios-camera-native-confirm-r1/artifacts PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_video_record_note.py::test_user_can_publish_video_record_note_for_review[publish-note-video-camera]' -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261106-ios-camera-native-confirm-r1/allure-results
VW_APPIUM_RUN_ID=20261106-ios-camera-native-confirm-r1 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.allure_history --platform ios
```

- 上述是本轮实际命令；重跑时更换 run ID 及对应产物目录，避免覆盖。
