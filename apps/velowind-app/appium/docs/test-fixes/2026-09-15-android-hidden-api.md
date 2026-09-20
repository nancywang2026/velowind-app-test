# 2026-09-15 Android 真机隐藏 API 初始化失败

## 范围与当前状态

- 用户要求：在 Android 真机运行首页四个视频用例并处理失败。
- 用例：`tests/message/test_home_video_playback.py::test_four_home_videos_play_normally`。
- 设备：`4ea581b6`，型号 `25113PN0EC`；状态：修复中，最后核实 2026-09-15。
- 历史：首页视频 iOS 修复记录不适用于本次会话创建权限错误。

## 失败证据

- 报告：http://127.0.0.1:49611/#suites/e2df1617c526fa8fd9b264b94f1409a1/5b6d4d0a0418218d/ ，后续 http://127.0.0.1:50687/#suites/e2df1617c526fa8fd9b264b94f1409a1/a48ff9e556995bd4/ 。均为 broken，无视频步骤截图。
- Appium 设置及恢复 `hidden_api_policy*` 时被系统拒绝：`SecurityException: WRITE_SECURE_SETTINGS`。
- 本地日志：`.tmp/android-home-videos-run.log`、`.tmp/android-home-videos-r2.log`，服务 `.tmp/appium-android-physical/appium-server.log`。
- 原始失败发生于 driver fixture，不是视频播放失败。会话清理错误也会覆盖原始设置失败；服务日志确认 put 和 delete 都被拒绝。

## 第 1 轮：原配置连续重跑

- `20260915-android-home-videos` 和 `20260915-android-home-videos-r2` 均 1 error，初始化失败，断言未执行。
- 用户表示普通 USB 调试及安全设置已开启；仍收到相同拒绝。建议拔插/重启并不能视为已经验证有效，实际是否执行未知。
- 未创建业务数据，清理不涉及；真机视频未验证。

## 第 2 轮：显式兼容选项

- 本地安装的 UiAutomator2 README 第 114 行明确支持 `appium:ignoreHiddenApiPolicyError`，用于厂商锁定策略设置的设备。
- 修改 `android_config.py`：增加默认 false 的配置字段，环境变量 `VW_ANDROID_IGNORE_HIDDEN_API_POLICY_ERROR=1` 显式启用；不更改视频断言或设备权限，不默认作用于其他设备。
- 该选项只允许会话继续尝试，并不保证自动化服务器可用；以真机结果为准。
- 运行前检查 adb 在线且无其他 pytest，未停止任何他人服务。
- 本轮命令：

```bash
VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_ANDROID_UDID=4ea581b6 VW_ANDROID_APP_ACTIVITY=.MainActivity VW_ANDROID_IGNORE_HIDDEN_API_POLICY_ERROR=1 VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 VW_APPIUM_RUN_ID=20260915-android-home-videos-r3 VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/message/test_home_video_playback.py::test_four_home_videos_play_normally -q -s --tb=short --alluredir=.tmp/appium-android/runs/20260915-android-home-videos-r3/allure-results
```

- 状态：运行中。日志 `.tmp/android-home-videos-r3.log`。

## 可复用方法与无效尝试

- 区分 adb 授权成功与系统设置写权限；不要将 device 状态或开关状态当作可写权限证明。
- 原配置重复运行没有解决问题；检查 Appium 服务日志而不只看 pytest 最后一个错误。

## 遗留项与交接

- 待核实兼容选项的真机结果及单元回归；当前不能宣称视频通过。

## 第 2 轮实际结果及交接

- 配置单元命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_android_config.py -q --tb=short`，17 passed，0.05 秒；`git diff --check` 通过。
- 真机 `20260915-android-home-videos-r3`：会话创建、页面读取及滑动成功，原初始化阻塞已解除。完整用例 **1 failed，79.80 秒**，新错误为“只找到 0/4 个不同视频”，详见独立记录 `2026-09-15-android-video-candidates.md`。绝不能标为视频通过。
- 系统权限没有被授予；只是使用驱动正式支持的显式兼容选项。普通运行必须显式设置 `VW_ANDROID_IGNORE_HIDDEN_API_POLICY_ERROR=1` 才启用。
- 业务清理：无新增业务数据，未涉及。pytest 已退出，设备会话已释放。
- 已完成本初始化兼容修改；其他设备、整套未验证。下一步需确认首页视频数据/识别情况。
