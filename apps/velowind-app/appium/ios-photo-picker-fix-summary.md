# iOS 发布图片选择修复总结

日期：2026-07-11  
分支：`f_refactor_speed`

## 背景

发布笔记真机用例 `publish-note-changbaishan` 在添加照片阶段不稳定：

- 测试数据指定相册为 `长白山`，但系统相册有时停留在上一次的 `云南洱海`。
- 进入相册后，缩略图已显示但没有稳定完成选择。
- 后续验证发现，照片选择成功后，发布结果页显示 `已发布`，但测试只识别 `成功`、`审核`、`待审核`，导致误判超时或失败。

## 修复方式

新增共享模块：

- `apps/velowind-app/appium/velowind_appium/modules/photo_picker.py`

发布活动和发布笔记都复用同一套系统相册选择流程：

- `activity.py` 通过共享模块选择活动图片。
- `message_detail.py` 通过共享模块选择笔记图片。

共享模块负责：

- 选择手机相册来源。
- 处理照片权限弹窗。
- 打开指定相册前，先切换到 `精选集`。
- 从当前相册页返回后，再进入测试数据指定的相册，例如 `长白山`。
- 批量选择相册内缩略图。
- 点击系统相册 `完成/Add` 按钮时，优先使用可见可用按钮的坐标点击。
- 如果第一次点击 `完成/Add` 后没有退出系统相册，继续重试，而不是把一次 `.click()` 假成功当作完成。

另外补齐了一个共享模块内缺失的坐标点击工具：

- `_tap_element_center()`

## 成功态修复

真机发布后实际进入详情页并显示 `已发布`。这代表发布已经完成，但原测试没有把它算作成功态。

因此补充：

- `NOTE_SUCCESS_TEXTS` 增加 `已发布`。
- `test_ios_publish_note.py` 的最终断言接受 `已发布`。
- `test_message_detail_helpers.py` 增加 `已发布` 成功态单测。

## 验证结果

本地 helper 验证：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  apps/velowind-app/appium/tests/test_photo_picker_helpers.py \
  apps/velowind-app/appium/tests/test_activity_helpers.py \
  apps/velowind-app/appium/tests/test_message_detail_helpers.py -q
```

结果：

```text
74 passed, 1 warning in 9.87s
```

发布笔记长白山真机验证：

```bash
PYTHONPATH=apps/velowind-app/appium python3 -m pytest \
  'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' \
  -q -m full
```

结果：

```text
1 passed, 1 warning in 488.41s (0:08:08)
```

## 结论

发布笔记 `长白山` 用例的添加照片问题已通过真机验证。当前活动和笔记的图片选择流程已统一复用 `photo_picker.py`，后续系统相册相关修复应优先在该共享模块内处理，避免两个发布流程再次分叉。
