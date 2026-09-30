# 2026-09-20 Android 拍摄视频被系统权限弹窗阻塞

## 范围与当前状态

- 用例：`test_user_can_publish_video_record_note_for_review[publish-note-video-camera]`。
- Android 真机；目标用例已通过，新增笔记实际清理成功；整套未验证。
- 历史参考：`2026-09-16-ios-photo-permission-picker.md`，仅参考入口未打开不能当成媒体失败的诊断原则；本次是 Android 首次相机授权弹窗。

## 失败证据

- 报告：`http://127.0.0.1:62798/#suites/8a1699b7f514293d5bbf66b4d6472144/ded253d5b8a26854/`。
- 原报告目录：`.tmp/appium-android/runs/20260920-131723-43137/allure-report/`。
- 失败步骤 `02-publish-note-for-review-publish-note-video-camera`，报错 `Video camera opened but recording could not be completed.`。
- 截图 `data/attachments/476721fbe6589bfe.png`、XML `64386ca85ce17dc3.xml` 显示 permissioncontroller 的“允许寻风集拍摄照片或录制视频？”弹窗，按钮“仅在使用中允许 / 本次使用允许 / 拒绝”；仍在发布表单，尚未打开相机。

## 第 1 轮：分析、修改与验证

- 已确认：权限处理仅在选择拍摄来源前执行；选择后出现的相机/麦克风授权没有处理；旧通用允许文字未覆盖此次 OEM 文案。
- 修改 `photo_picker.py`：Android 等待相机控件时处理系统相机/麦克风授权；只匹配系统 permissioncontroller、媒体授权提示和准确的使用中允许按钮，连续处理相机及麦克风弹窗，随后仍需实际相机 toolbar 出现。等待上限 15 秒。
- 新增相机、麦克风授权回归及非系统页面、非媒体权限拒绝匹配测试。
- 真机前检查无运行中 pytest；4725 日志确认上个 session 已删除，未终止其他服务。
- 单元与目标真机结果待追加；原失败没有发布，无新增笔记清理任务。

## 遗留项

- 运行目标真机用例，分别核对拍摄/发布断言和实际清理结果；整套未验证。

## 第 1 轮验证结果

- 单元：`VW_APPIUM_AUTO_OPEN_REPORT=0 VW_NOTE_CLEANUP_MODE=ui PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_android_camera_cleanup.py apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py -q`，**84 passed / 39.42 秒**。
- 真机命令：

```bash
VW_API_ENV=prod VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_ANDROID_UDID=YHK7EERSGAPZX87X VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 VW_APPIUM_AUTO_OPEN_REPORT=0 VW_APPIUM_RUN_ID=20260920-android-camera-permission-fix PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_video_record_note.py::test_user_can_publish_video_record_note_for_review[publish-note-video-camera]' -q -s --alluredir=.tmp/appium-android/runs/20260920-android-camera-permission-fix/allure-results
```

- 真机 **1 passed / 126.79 秒**；准备首页、拍摄视频发布、清理三步骤均 passed。预览实际时长附件为 4 秒（配置录制 5 秒，保持原有时长校验逻辑）。
- API DELETE `pst-e1eb9b73206c48fcbe7551af64df10cc` passed；`publish-note-cleanup-result` 显示 deleted 包含本轮标题、skipped=[]，无 cleanup-pending。
- 报告：`.tmp/appium-android/runs/20260920-android-camera-permission-fix/allure-report/`；原始附件同级 `allure-results/`；日志 `.tmp/android-camera-fix/pytest.log`。
- `git diff --check` 通过。无失败修复尝试；原失败报告保留。设备 session 已正常释放，未重置系统权限。
- 验证边界：当前设备完成目标发布流程；没有重置权限来强制重复所有首次授权组合，连续权限弹窗各 OEM 变体及整套未验证。
- 已完成本次修复和目标真机验证；未修改业务 App、清理环境默认值或原有发布/清理断言。
