# 2026-10-27 iOS 发布入口点击后无跳转

## 范围与当前状态

- 用户要求：修复所链接报告中的测试用例。
- 用例：`tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]`。
- 模块：`velowind_appium/modules/message_detail.py` 的发布入口。
- 平台：iOS 真机，bundle `com.velowind.rider`；本轮未核实 App 版本；原运行 `no_reset=false`。
- 当前状态：入口修复完成；独立生产配置下完整真机目标 1 passed，本轮新增笔记实际删除成功。最后核实：2026-10-27。
- 历史参考：[发布详情与清理](2026-09-15-ios-publish-cleanup.md)、[首页 Button 卡片](2026-10-19-home-note-button-cards.md)。本次尚未进入表单，与历史详情误选不同；遵循会话不竞争要求。

## 失败证据

- 原运行：`20261027-144612-36760`，目录 `.tmp/appium-ios/runs/20261027-144612-36760/`。
- 临时 URL：http://127.0.0.1:62063/#suites/a315921332822b24a92de7455c3da80b/d3c37adb04795bc9/
- 步骤 `02-publish-note-for-review-publish-note-changbaishan` 失败：`Clicked accessibilityId=bottom-nav-center-action, but no publish sheet, note form or login page appeared within 10 seconds`。
- 原报告附件：`allure-report/data/attachments/72debc92d75cc638.png`、`7b070dca42bff71c.xml`。
- 截图显示活动列表及底部加号，没有发布面板。XML 中入口可见、enabled=true，矩形 x=160,y=795,width=82,height=39。
- 原运行在发布前失败，未新增本用例笔记，未进入清理。

## 第 1 轮：现场调查与基线复跑

### 分析

- 已确认：旧 iOS 分支只按稳定 accessibility ID 点击一次并等待 10 秒，无跳转即失败。
- 已确认：检查进程时无正在运行的 pytest；原报告已经完成，未终止其他 Appium / WDA 进程。Appium session discovery 未启用，未更改服务器安全配置。
- 现场调查：`no_reset=true` 连接同一真机，在活动页点击同一 ID，2 秒后正常出现“选择发布类型”面板。附件 `.tmp/appium-ios/runs/20261027-publish-entry-investigation/{before.xml,after-click.xml,after-click.png}`。因此并非稳定 ID 失效或面板文案不兼容。
- 推测：原冷启动后入口尚未完成交互就绪，首击未生效；单次成功不能确认具体 App 内部原因。正在按原配置复跑完整用例，区分偶发入口失败与后续独立问题。

### 修改与验证

- 代码修改：尚未执行。
- 基线命令：

```bash
VW_APPIUM_RUN_ID=20261027-publish-entry-baseline \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261027-publish-entry-baseline/artifacts \
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' \
-q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261027-publish-entry-baseline/allure-results
```

- 单元检查：未执行。
- 真机：局部同 ID 点击成功；完整基线运行中，不能计为通过。
- 清理：现场调查未提交内容；基线待结果。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 核对失败截图、XML 与稳定 ID 的现场点击 | 点击返回但页面没变化 | 入口仍有效；不能将原超时归为文案错误 |

## 遗留项与交接

- 已完成：原失败证据与单次现场点击核实。
- 未完成：修复、单元验证、完整真机验证及清理核验。
- 下一步：观察基线结果，在保持状态断言和稳定 ID 的前提下处理首击未生效。
- 设备占用：本轮基线 pytest 独占使用中，勿另建会话。

## 第 1 轮结果：基线未复现入口失败，出现独立权限阻塞

- 原配置完整基线 **1 failed / 56.72 秒**；首页准备 1.9 秒通过，发布步骤 46.5 秒失败。此次成功打开发布表单，在选图阶段报“相册访问被权限提示阻塞”。这不是入口修复结果（当时尚未改代码）。
- 报告目录 `.tmp/appium-ios/runs/20261027-publish-entry-baseline/`，附件 `artifacts/20261027-145134-test_user_can_publish_note_for_review-publish-note-changbaishan.{png,xml}`。
- 参考 [历史照片权限记录](2026-09-16-ios-photo-permission-picker.md)：保持已确认的权限阻塞断言，未重置或自动修改用户的系统照片权限。已请求用户授权后继续完整复跑。
- 清理：未选择图片、未提交，无本轮新增笔记或清理目标。

## 第 2 轮：首击未跳转时按同一 ID 重试一次

### 分析与修改

- 根因边界：原报告确认点击返回但无跳转；当前无法稳定复现，冷启动交互时机仍属推测，不宣称修复 App 内部原因。
- `message_detail.py::_tap_publish_entry_if_present`：保留首击等待 10 秒；超时后再次检查面板、表单和登录页，目的页已出现就停止；否则重新按同一稳定 ID 查找，仅按钮仍可见且可用时再点击一次，并等待真实跳转。
- 最多两次点击，无坐标或模糊文字回退；两次失败仍抛断言，设备错误仍向上传递。正常成功路径不增加额外等待。
- `test_message_detail_helpers.py`：覆盖首击无效后二次成功、迟到面板不得重复点击、入口消失/隐藏/禁用时不再点击、两次超时及登录跳转。

### 验证

```bash
VW_NOTE_CLEANUP_MODE=ui VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q -k publish_entry

VW_NOTE_CLEANUP_MODE=ui VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py apps/velowind-app/appium/tests/unit-test/test_photo_picker_helpers.py -q
```

- 定向单元：**17 passed / 216 deselected / 0.19 秒**，其余消息和相册单元回归进行中。
- 修复后真机：`.tmp/appium-ios/runs/20261027-publish-entry-fixed-probe/`，使用原配置冷启动，调用 `ensure_logged_in_for_publish_entry`、`open_message_note_publisher` 并验证 `message_note_form_is_visible`，正在执行。该探测只验证入口到表单，不选图或提交。
- 完整真机发布和实际清理：等待照片权限后验证，未通过。

### 第 2 轮阶段结果

- 消息 / 相册单元完整回归：**307 passed / 60.96 秒**，只有既有 LibreSSL warning；`git diff --check` 通过。
- 修复后冷启动真机入口探测：**通过**，已进入发布表单，`note-form.xml`、`note-form.png` 保存于上述 fixed-probe 目录；未提交，无需清理。该次未观察到首击超时，二次点击路径目前由单元验证。
- 用户确认“已授予照片权限”，继续完整目标复跑，run `20261027-publish-entry-fixed-full`。显式 `VW_IOS_NO_RESET=true` 保持用户刚授予的权限，其余使用仓库配置；未修改全局 yaml 或系统权限。
- 复跑前检查无其他 pytest 进程；本轮会话独占设备。完整结果及实际清理待落盘。

```bash
VW_IOS_NO_RESET=true VW_APPIUM_RUN_ID=20261027-publish-entry-fixed-full VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261027-publish-entry-fixed-full/artifacts VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' -q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261027-publish-entry-fixed-full/allure-results
```

### 第 2 轮完整真机结果（保留失败）

- run `20261027-publish-entry-fixed-full`：**1 failed / 172.83 秒**；准备 1.9 秒 passed，发布与图片内容校验 **161.8 秒 passed**，API 清理 **0.8 秒 failed**。
- 入口超时本轮未出现；用户授予照片权限后成功选图、填写内容、发布并验证图片。不能将发布步骤通过记为整条通过。
- 清理响应 HTTP 400 / code `17210004` / `post.not_found`，目标 `pst-5227a8b35dcf4759ad3db2daf77dbb5f`，地址 `https://dev-api.velowind.com/api/v1/mobile/posts/<postId>`；traceId `6a589c90-a8f1-4973-947e-48fe7b0f1e9a`。
- 已保存唯一 publication ID，但本次删除未成功；不能将 not_found 当作删除成功。独立问题后续见 [API 清理目标不存在](2026-10-27-note-cleanup-post-not-found.md)。
- 设备会话已正常退出，无运行中设备 pytest。完整用例与实际清理待继续验证。

## 当前交接状态

- 已完成：入口按同一 ID 最多重试一次；307 项相关单元通过；修复后真机入口、选图、发布、图片内容校验通过。
- 未完成：完整用例仍因 API DELETE `post.not_found` 失败；新增笔记尚未确认清理，详情见独立清理记录。
- 等待用户确认当前 App 实际连接 test / uat / prod；收到后按确定环境继续清理与完整复跑。
- 本轮报告 `.tmp/appium-ios/runs/20261027-publish-entry-fixed-full/allure-report/` 已实际生成；`git diff --check` 通过。真机会话已退出，未停止他人服务。

### 接续状态：生产地址已确认

- 用户确认 App 连接生产环境，API host 为 `https://prod-api.velowind.com`；已修正 cleanup.yaml 默认地址并同步 README。
- 生产登录拒绝当前本地凭据（10011023 / Incorrect password），尚未发送 DELETE。当前待有效生产凭据，未重复发布、未新建真机会话。
- 原入口修复的 307 项单元及真机发布校验通过结论不变；完整用例和清理尚未通过。后续过程见独立清理记录第 2 轮。

## 最终验证结果

- 用户提供有效生产凭据并解锁后，`20261027-prod-publish-unlocked` 完整目标 **1 passed / 166.91 秒**；入口、图片发布与内容校验、生产 API 清理全部通过。
- 本轮新增 ID `pst-b628261e44844719a4afc8050ae94ab2` 的生产 DELETE HTTP 200、deleted=true，cleanup-result 为 deleted、skipped=[]，无 pending。只代表本轮新增笔记，旧 ID 处理边界见独立清理记录。
- 消息/相册单元 307 passed；入口二次点击路径由单元覆盖，本轮真机未观察到首击超时，不宣称稳定复现并消除了 App 内部时序原因。
- 报告 `.tmp/appium-ios/runs/20261027-prod-publish-unlocked/allure-report/` 已实际生成；整套未执行；设备会话已正常退出。
