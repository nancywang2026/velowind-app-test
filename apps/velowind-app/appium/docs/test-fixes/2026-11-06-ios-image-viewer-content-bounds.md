# 2026-11-06 iOS 大图查看器黑边导致图片比对失败

## 范围与当前状态

- 用户要求：修复报告中的图片发布用例。
- 用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`。
- 涉及模块：`message_detail.py` 图片截图、`image_validation.py` 图像区域计算。
- 平台：iOS 真机；原报告窗口 402×874，PNG 1206×2622；报告环境记录 iOS 26.2.1；App 版本尚未核实。生产环境登录和 API 清理。
- 当前状态：已修复，完整目标真机 1 passed，本轮新增笔记 API 删除成功；联合单元 245 passed、5 项历史 mock 失败。
- 最后核实时间：2026-11-06（Asia/Shanghai）。
- 历史参考：[详情标题标识](2026-11-06-ios-published-detail-title-id.md)、[发布详情与清理](2026-09-15-ios-publish-cleanup.md)。本报告已打开正确图片查看器，独立于此前标题识别问题。

## 失败证据

- 运行：`20261106-144932-23504`；报告 `.tmp/appium-ios/runs/20261106-144932-23504/allure-report/`。
- URL：`http://127.0.0.1:60449/#suites/a315921332822b24a92de7455c3da80b/3913f15643a55dd7/`。
- 步骤：`02-publish-note-for-review-publish-note-changbaishan`。
- 报错：`pixel-delta-too-high`，source_size=(709,942)，actual_size=(1110,2414)，mean_pixel_delta=61.596215986394554。
- 附件（相对于报告 `data/attachments/`）：源图 `33c5df75bbb75745.png`；比对截图 `c87ae0dfdc9f0253.png`；失败整屏 `4d51dff632238536.png`；XML `910117d667c94224.xml`；比对摘要 `ac7984f26bfd7997.txt`。
- 现场观察：所选长白山图片与大图截图场景一致；大图截图包含上下黑边、状态栏与关闭按钮。XML 的可见 Image 节点及 `post-detail-preview-pager` 均为 402×874，全屏节点不等于图片实际内容区域。
- 预期：仅比对展示图片的内容；实际：整张查看器参与缩放比对。
- 本轮尚未清理原失败笔记；原报告因断言失败未进入成功后清理。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：`_open_published_note_image_viewer` 返回全屏 Image bounds，`_capture_image_bounds` 按此截图；比对器只裁 4% 内边距，无法去掉大面积留黑。
- 拟修复：仅在明确可见的 iOS 大图查看器中，按所选源图宽高比和查看器 bounds 计算居中 contain 内容区域。保留原像素阈值与目标标题核验，普通详情 / Android 沿用原路径。
- 待验证：原失败截图按该区域裁剪后的比对结果、错误图片拒绝、完整真机发布和清理。

### 修改

- `image_validation.py` 新增 `contained_image_bounds`，按源图比例计算居中 contain 区域。
- `message_detail.py` 只在平台 iOS 且 `post-detail-preview-pager` 可见时使用此区域；保留原图片内容比对、阈值、目标标题核验，其他页面和 Android 沿用原路径。
- `test_publish_note_image_validation.py` 新增 6 项检查：横 / 竖图、长图留边、满屏、三倍截图相同图片通过及镜像错误图片失败。

### 验证

- 已检查进程：无 pytest；现有 Appium 4723 与 WDA 保留，没有结束其他进程。
- 原失败证据复算：裁剪后 source_size=(709,942)，actual_size=(1110,1475)，mean_pixel_delta=4.1016424619640395，原阈值 18 下通过；裁剪证据 `.tmp/appium-ios/image-viewer-bounds-debug/report-cropped.png`。此结果不代替真机完整验证。
- 单元命令：`PYTHONPATH=apps/velowind-app/appium VW_APPIUM_AUTO_OPEN_REPORT=false .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_publish_note_image_validation.py apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q`。
- 单元结果：245 passed、5 failed，30.78 秒；run `20261106-154220-29764`。新增 6 项均通过；5 项失败与历史标题修复记录所列发布 mock 失败一致（2 项裸 object 不支持 `_api_note_publication`，3 项 FakeDriver 缺 `find_element`），不称全文件通过；本轮未另做修改前基线隔离。
- 静态：涉及本轮修改文件的 `git diff --check` 通过。
- 真机命令：`VW_API_ENV=prod VW_IOS_NO_RESET=true VW_APPIUM_CAPTURE_FINAL_PAGE_ON_PASS=true PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.run_ios_tests --suite apps/velowind-app/appium/test-suites/ios-publish-note.yaml`。
- 真机：`20261106-170150-36850`，1 passed，270.10 秒。发布步骤 190.2 秒（包含图片身份 / 内容核验），清理步骤 0.5 秒。结果为原目标单例通过，不外推为整套通过。
- 报告：`.tmp/appium-ios/runs/20261106-170150-36850/allure-report/`；临时 URL `http://127.0.0.1:53639/`。
- 清理：附件 `publish-note-cleanup-result` 确认 deleted=[请求标题]、skipped=[]；生产环境匹配正确；本轮发布 post ID `pst-83dbca5e42674a128d5bc5f82cd3eaa2`。未发现 cleanup-pending，新增笔记实际删除成功。原失败笔记未执行删除，不能与本轮清理混为一谈。
- 本轮结论：有效，原图片比对误报修复后完整目标真机通过；会话已退出。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 对照 XML Image bounds 与实际 PNG 内容 | contain 展示图片 | XML 可能给全屏容器，不能直接认定是内容 bounds |
| 放宽像素阈值 | 本轮不采用 | 会掩盖错误图片，不解决黑边进入比对的问题 |

## 遗留项与交接

- 已完成：原证据核实、修复、新增回归通过、原失败图片裁剪复算、原目标真机完整通过、本轮新增笔记实际删除。
- 未完成 / 未验证：整套测试未重跑；历史 5 项发布 mock 失败本轮未修；原失败笔记未清理。
- 下一步：如继续处理历史遗留，应按原报告 post ID 精确核对后清理，不能删除其他笔记。
- 设备占用：本轮 pytest 已结束，driver 已退出；保留原有 Appium / WDA 与 Allure 报告服务。
