# 2026-11-05 Android 选图忽略指定影集

## 范围与当前状态

- 用户要求：修改脚本，使用“长白山”影集。
- 用例：`publish-note-changbaishan` 图片笔记；模块：`photo_picker.choose_local_photo`。
- 平台：Android 真机 YHK7EERSGAPZX87X；本轮未核实系统 / App 版本；未更改清理模式。
- 当前状态：代码已修改；首轮单元 308 passed / 1 failed，更新旧断言后该项复验 1 passed；真机重跑 1 failed，系统选择器未展示长白山影集，未发布。
- 最后核实时间：2026-11-05。
- 历史参考：[照片权限误判](2026-09-16-ios-photo-permission-picker.md) 属于 iOS 权限问题，不能解释本次 Android 错误影集；[会话冲突记录](2026-09-15-ios-publish-cleanup.md) 提醒避免替换现有会话。

## 失败证据

- 用户观察：自动化进入影集后选择“相机”中的其他照片。
- 只读 ADB 检查确认 `/sdcard/Pictures/长白山/` 只有 `2FDBA948-84E8-44E6-81ED-BC704ADF5DC9_1_105_c.jpeg`，250119 字节。
- 手机文件和本地同名素材 SHA-256 一致：`7c53ec4706232ab70507ab65919c907740387909330c907607f770e175fcaaa7`；本地预览为湖泊、山脉、蓝天白云。
- 最近报告参考：`.tmp/appium-android/runs/20261105-171400-95328/`；本轮未从该报告确认完整选图过程，不把用户反馈当作已独立复现。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：Android 分支把 `album_name` 强制替换为“相机”，且系统 Photo Picker 分支将序号重置为 1、清空多选序号。即使指定“长白山”，也不会进入目标影集。
- 已确认：图片发布 YAML 的 `album` 实际为“图片”，需同步改成“长白山”。
- 未确认：用户那次运行实际选中的文件名；本轮不据此声称已完整复现。

### 修改

- `velowind_appium/modules/photo_picker.py`：按传入影集打开，删除强制首张和清空多选的覆盖逻辑；保留 Android 目标影集打开失败就停止的行为。
- `tests/message/testdata/publish_notes.yaml`：图片笔记配置改为 `album: 长白山`；视频配置不变。
- `tests/unit-test/test_photo_picker_helpers.py`：回归验证 Android 指定影集和序号得到保留；目标影集缺失时不得选图或退回其他来源。
- `tests/unit-test/test_message_detail_helpers.py`：加载真实配置时断言影集为“长白山”。

### 验证

从 `apps/velowind-app/appium` 执行：

```bash
VW_NOTE_CLEANUP_MODE=ui /Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest tests/unit-test/test_photo_picker_helpers.py tests/unit-test/test_message_detail_helpers.py -q
```

- 首轮单元：308 passed / 1 failed，61.05 秒。失败项 `test_build_changbaishan_note_draft_uses_requested_content` 仍期待“图片”，实际读到“长白山”；运行中更新文件不会改变该进程已加载的断言。原失败保留。
- 首轮报告 / timing：`.tmp/appium-ios/runs/20261105-173355-97993/timing/main-97993-1793871235201105000`（单元框架默认目录名含 ios，不是真机报告）。
- 此环境变量仅隔离单元中的 API 清理分支。新增指定影集 / 序号和缺失影集停止检查均通过。
- 真机：未运行，无本轮真机报告目录；未验证完整发布。
- 清理：未发布或删除业务数据，不涉及实际清理。

## 第 2 轮：旧配置断言更新后复验

- 修改：将默认草稿构建测试的旧“图片”断言同步为“长白山”。
- 命令：同目录执行 `VW_NOTE_CLEANUP_MODE=ui /Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest tests/unit-test/test_message_detail_helpers.py::test_build_changbaishan_note_draft_uses_requested_content -q`。
- 结果：1 passed，0.14 秒；首轮其余 308 项通过，本轮仅复验该失败项，未声称重新完整跑过 309 项。
- timing：`.tmp/appium-ios/runs/20261105-173508-98419/timing/main-98419-1793871308564741000`。
- `git diff --check` 通过。两轮均有现有 urllib3 / LibreSSL 环境警告。
- 真机与完整发布：未验证；清理不涉及。

## 第 3 轮：用户要求真机重跑

### 执行与失败证据

- 重跑前重新检查进程：未见 pytest；复用已有 Appium 4725，不结束其他进程；连接设备仍为 YHK7EERSGAPZX87X。
- 依照此前运行环境使用生产配置，目标仅为图片用例，不运行视频或整套。
- 工作目录 `apps/velowind-app/appium`，命令：

```bash
VW_API_ENV=prod VW_ANDROID_TARGET=physical VW_ANDROID_UDID=YHK7EERSGAPZX87X VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 VW_ANDROID_IGNORE_HIDDEN_API_POLICY_ERROR=true VW_APPIUM_RUN_ID=20261105-changbaishan-album-r1 VW_APPIUM_ARTIFACT_DIR=/Users/test/Documents/velowind-app-dev-test/.tmp/appium-android/runs/20261105-changbaishan-album-r1 VW_APPIUM_CAPTURE_EACH_STEP=1 VW_PHOTO_PICKER_DEBUG=1 /Users/test/Documents/velowind-app-dev-test/.venv/bin/python -m pytest 'tests/android_smoke/test_android_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' -q -s --alluredir=/Users/test/Documents/velowind-app-dev-test/.tmp/appium-android/runs/20261105-changbaishan-album-r1/allure-results
```

- 结果：**1 failed / 55.23 秒**；首页准备通过，发布步骤在选图阶段失败（27.2 秒），错误 `Photo selection did not complete`。未提交发布，未执行清理，不存在本轮新增已发布笔记的清理目标。驱动已在 teardown 退出。
- 注意：`VW_PHOTO_PICKER_DEBUG` 并非实际调试开关；代码读取的是 `VW_APPIUM_DEBUG`，本轮没有选图 debug 文本，不能假称日志已确认整个路径。
- 报告目录：`.tmp/appium-android/runs/20261105-changbaishan-album-r1/allure-results/`；HTML 为同级 `allure-report/`，无本轮 HTTP 地址。
- XML：同运行目录 `20261105-174104-test_user_can_publish_note_for_review-publish-note-changbaishan.xml`；截图为同名 `.png`；`live-screen.png` 是运行中“全部”页快照，不能用它代替最终“影集”页证据。

### 新发现与后续

- 已确认 XML 中前台为 `com.android.photopicker`，`content-desc=影集` 且 `selected=true`，说明已切到影集；可见影集只有“相机”“屏幕截图”，没有“长白山”。滚动查找后仍失败，脚本未退回“相机”选任意照片。
- ADB MediaStore 查询同名文件发现三条索引：`Pictures/长白山/`、`Pictures/Gallery/owner/长白山/`、`DCIM/Camera/`，前两条 `bucket_display_name=长白山`。因此不能归因于文件未存入或未索引。
- 尚未确认：此系统选图器隐藏自定义影集的具体系统原因；不能声称改名或重新同步一定有效。
- 失败后额外点开“功能设置”检查，仅显示隐私保护弹窗（抹去位置 / 拍摄信息），XML 为 `picker-menu.xml`；通过返回键关闭，未更改设置。该入口不能用于切换到自定义影集。
- 本轮无新的代码修改。下一步需验证此机型支持的自定义影集选择入口，再适配并重跑；不能将单元通过作为真机选图完成的依据。

### 第 3 轮后续只读核查：为什么影集不显示

- 设备系统 Android 16；`com.android.photopicker` versionName=16、versionCode=36，安装在 MediaProvider APEX 中，确认为系统选图器。
- 同名文件 MediaStore 中的两条长白山记录均为 `image/jpeg`、`is_pending=0`、`is_trashed=0`，有独立 bucket_id，排除“尚在写入”“回收站”“未形成媒体目录索引”。
- [AOSP 分类组织实现](https://android.googlesource.com/platform/packages/providers/MediaProvider/+/ae8cbaf720b897031ae2c66adc002df27b59f48f/src/com/android/providers/media/photopicker/util/CategoryOrganiserUtils.java) 描述收藏、相机、视频、截图、下载及云端影集的排序。结合本机只显示内置分类的现场，推断当前系统选择器没有把本地自定义目录暴露为影集；没有反编译此机型 APK，不能将 AOSP 代码当作已核实厂商全部实现。
- 更正前置假设：`Pictures/长白山/` 是素材保存位置，但不能保证它会成为本机系统选图器中可点击的“长白山”影集。只改 `album_name` 无法创建系统选择器没有暴露的入口。

## 第 4 轮：实际安装代码与运行日志确认原因

- 用户要求：查明影集没有长白山的原因；本轮仅诊断，没有修改手机设置、权限或选图器组件。
- 进程核查未见 pytest；没有创建 Appium 会话，也没有中断 Appium 4725。
- `dumpsys activity activities` 确认 App 通过 `android.intent.action.GET_CONTENT`、`image/*` 进入 `com.android.photopicker/.hyper.HyperMainActivity`，不是打开小米相册首页。
- `dumpsys package com.velowind.rider` 确认本机 App 1.3.6 / versionCode 49、targetSdk 34，`READ_MEDIA_IMAGES` 已授予；不能把本次无影集归因于图片权限被拒绝。
- 从设备只读拉取实际安装的 Photopicker.apk、MediaProvider.apk 至 `.tmp/album-forensics/`，使用 Android SDK `apkanalyzer dex code` 查看实际 DEX，未使用其他机型源码代替本机证据。
- **代码确认**：`ExternalDbFacade.<clinit>` 中 `LOCAL_ALBUM_IDS` 固定为 `Camera`、`Screenshots`、`Downloads`；`queryAlbums` 遍历该数组生成本地影集，没有遍历所有 MediaStore 的 `bucket_display_name`。证据 `.tmp/album-forensics/ExternalDbFacade.smali:382` 和 `:1627`。
- `PickerDataLayerV2.queryCategoriesAndAlbums` 合并本地影集和额外数据源的分类；额外分类依赖非空 provider 及 gallery categories 开启，代码保存在 `.tmp/album-forensics/PickerDataLayerV2.smali`。
- **运行状态确认**：MediaProvider dump 显示 `isCloudMediaInPhotoPickerEnabled=false`、`allowedCloudProviderPackages=[]`、`mCloudProvider=null`、`allAvailableCloudProviders=[]`；精简证据 `.tmp/album-forensics/provider-config.txt`。
- **对应失败时间的日志确认**：17:40:53 `useGalleryCategories:false`；`Cannot fetch cloud categories when cloud authority is null.`；本地返回 Camera 27 张、Screenshots 113 张；Downloads 因无数据跳过；`Cannot fetch cloud albums when cloud authority is null.`。日志保存 `.tmp/album-forensics/picker-data-log.txt`。
- 已确认结论：这台手机本次系统“安全访问”选图路径仅展示固定本地分类，且扩展相册数据源关闭，因而不将已索引的“长白山”目录作为影集展示。该结论现已由本机代码、配置和对应时间运行日志共同支持，不再仅为基于 AOSP 的推断。
- 边界：未核实扩展数据源被关闭的厂商配置来源；未验证开启后是否能展示该目录，不擅自改系统全局开关。不要将结论推广为所有 Android 或所有小米版本都不能显示自定义影集。
- 真机完整用例结果仍为第 3 轮的 1 failed；本轮没有重跑用例、没有发布业务数据或执行清理。若要继续达成指定素材选图，需要适配可用的相册入口，或在“全部”中精确识别素材；方案尚未实施。

## 第 5 轮：验证小米相册入口及历史对照

- 当前无 pytest；使用独立 ADB Intent 诊断，不修改默认处理器、不禁用系统组件、不创建 Appium 会话。
- `cmd package query-activities` 确认同一 `GET_CONTENT image/*` 同时存在多个处理器：当前 HyperMainActivity 优先级 1000，AOSP 接管入口 105，DocumentsUI 100，小米相册 PickGalleryActivity 为 0。`resolve-activity` 当前选择 HyperMainActivity。
- 使用 `adb -s YHK7EERSGAPZX87X shell am start -a android.intent.action.GET_CONTENT -c android.intent.category.OPENABLE -t 'image/*' -p com.miui.gallery` 明确指定相册包。进入“影集”后，XML 前台为 `com.miui.gallery`，显示“图片”“长白山”“杭州西湖”“张家界”。点击“长白山”进入单张照片页，未点击照片或提交。
- 证据 `.tmp/album-forensics/miui-picker.xml`、`miui-albums.xml`、`miui-albums.png`、`miui-changbaishan.xml`。此独立诊断证明该入口能显示影集，不代表 App 发起的选图请求已改为此入口，也不代表选择结果能从独立 ADB 启动返回 App。
- 历史 XML `.tmp/appium-android/20260724-141130-test_user_can_publish_note_for_review-publish-note-changbaishan.xml` 等存在 `com.miui.gallery` 选图界面；当前失败 XML 则是 `com.android.photopicker`。支持“选图处理入口发生变化”，即使 App 发出相同通用 Intent，也不能保证由同一系统组件处理。
- 当前系统 `OS3.0.307.0.WONCNXM`，构建日期 2026-09-04；选图器包时间显示 2026-03-20。没有历史系统配置 / Intent 解析快照，不能据此确认是哪次更新、默认设置或开关导致切换。
- 用户强调 App 逻辑没变：无需先假设 App 代码回归；可确认的是当前通用请求解析为“安全访问”，旧证据和直接相册诊断使用的是小米相册。优先调查入口路由变化。此前建议修改 App 是一种显式固定入口的方案，并非已证明唯一或必须的修复。
- 真机发布结果仍为第 3 轮失败；本轮仅入口显示验证，无发布 / 清理。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| ADB 文件列表及哈希核对 | 设备在线且只读访问素材 | 确认手机素材与本地一致，不能据此确认选择器选中了它 |
| 固定“相机”第一张 | 需要指定影集素材时 | 原逻辑不适用，相机排序不能保证目标素材身份 |

## 遗留项与交接

- 已完成：原因确认、公共逻辑及用例配置修改。
- 待完成：解决当前系统选图器不展示“长白山”影集的问题，真机确认选中目标图；完整发布和整套未验证。
- 进程检查：已有 Appium 4725 及 Allure 报告进程，检查时未见 pytest；未创建或替换 Appium 会话，未终止其他任务。
