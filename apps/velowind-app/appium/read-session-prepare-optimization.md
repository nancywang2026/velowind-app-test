# Read Session Prepare Optimization

## Scope

本次只优化读操作相关测试的首页准备步骤，不改发布笔记和发布活动相关用例。

当前试点范围：

- `tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough`
- `tests/message/test_ios_search_by_type.py::test_user_can_filter_notes_by_type`
- `velowind_appium.session.ensure_read_session_on_home`

未改动：

- 发布笔记测试
- 发布活动测试
- 发布入口专用 helper
- 全局 `logged_in_session` fixture

## Problem

历史 Allure 结果中，读用例的 `01-prepare-home-session` 常见耗时约 20-26 秒。代码调查显示，测试进入用例前已有 autouse fixture 运行一次 `prepare_logged_in_session(...)`，测试体内又显式执行一次 `prepare-home-session`。

在这种场景下，显式 step 通常只是再次确认已经在首页，但旧路径仍会尝试点首页并等待首页 feed，因此存在明显重复成本。

## Change 1

新增 `ensure_read_session_on_home(driver, ios_config)`：

- 如果 `_home_visible(driver)` 已经为真，立即返回，不再关弹窗、点协议、点首页或等待 feed。
- 如果当前不是首页，则保留原来的安全路径：先处理常见弹窗和协议，再检查首页；仍不是首页时 fallback 到完整 `ensure_logged_in_on_home(...)`。

试点读用例 `test_ios_feature_walkthrough` 的显式 `01-prepare-home-session` 改为调用这个读用快速 helper。

## Change 2

在真机验证 `test_ios_feature_walkthrough` 通过且 `01-prepare-home-session` 明确降到 3.7 秒后，继续做一个小范围读用例试点：

- `tests/message/test_ios_search_by_type.py::test_user_can_filter_notes_by_type`

该用例只浏览笔记 feed、切换笔记类型并等待筛选结果，不涉及发布笔记或发布活动。变更仅把显式 `prepare-home-session` 从完整 `ensure_logged_in_on_home(...)` 替换为 `ensure_read_session_on_home(...)`。

## Unit Verification

先写失败测试：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q -k 'ensure_read_session_on_home'
```

结果：2 个测试失败，原因是 `session.ensure_read_session_on_home` 尚不存在。

实现后验证：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q -k 'ensure_read_session_on_home'
```

结果：`2 passed, 56 deselected`。

扩展相关 session 测试：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q -k 'ensure_read_session_on_home or ensure_logged_in_on_home'
```

结果：`13 passed, 45 deselected`。

试点用例收集检查：

```bash
.venv/bin/python -m pytest 'apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough' --collect-only -q
```

结果：`1 test collected`。

## Real Device Verification

基准命令使用配置中的 iPhone UDID：

```bash
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/read-prepare-optimization-baseline/allure-results \
  --clean-alluredir
```

结果：测试 setup 未开始成功，Appium 返回 `Unknown device or simulator UDID: '00008150-0006799C2693401C'`。

设备发现状态：

- `xcrun xctrace list devices` 将 `Zhigang的iPhone (26.2.1) (00008150-0006799C2693401C)` 列在 `Devices Offline`。
- `xcrun devicectl list devices` 显示同一台 `Zhigang的iPhone` 为 `available (paired)`，CoreDevice identifier 为 `713FC5A1-02ED-51AE-99C8-4B2B5CBBFFFD`。
- 使用 CoreDevice identifier 再跑一次，Appium 仍返回 `Unknown device or simulator UDID: '713FC5A1-02ED-51AE-99C8-4B2B5CBBFFFD'`。

随后 `xcrun xctrace list devices` 能看到 `Zhigang的iPhone` 在线，继续运行优化后试点用例：

```bash
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/read-prepare-optimization-optimized/allure-results \
  --clean-alluredir
```

结果：测试仍未进入用例体，WDA 启动 `/status` 60s 超时。

Appium log 中出现：

- `RemoteXPC devices listing unavailable`
- `Please run the tunnel creation script first`

尝试启动 xcuitest driver tunnel 脚本：

```bash
appium driver run xcuitest tunnel-creation
```

结果：脚本要求 root/admin，例如 `sudo appium driver run xcuitest "tunnel-creation"`。当前执行环境不能 sudo，因此未启动 tunnel。

再尝试仅增加 WDA timeout：

```bash
VW_IOS_WDA_LAUNCH_TIMEOUT=180000 \
... \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/read-prepare-optimization-optimized-timeout180/allure-results \
  --clean-alluredir
```

结果：仍未进入用例体，WDA `xcodebuild failed with code 65`。

因此当前阻塞在 WDA/Appium 真机启动层，无法完成真机耗时对比。

### WDA Recovery

手机连上网后，先确认 CoreDevice 状态：

- `developerModeStatus: enabled`
- `pairingState: paired`
- `transportType: wired`
- `tunnelState: connected`

设备上存在残留 WDA runner：

- `com.velowind.rider.WebDriverAgentRunner.xctrunner`

清理命令：

```bash
xcrun devicectl device uninstall app --device 00008150-0006799C2693401C com.velowind.rider.WebDriverAgentRunner.xctrunner
```

结果：`App uninstalled.`

随后启动干净 Appium server：

```bash
appium server \
  --address 127.0.0.1 \
  --port 4726 \
  --use-drivers=xcuitest \
  --log .tmp/appium-ios/wda-recovery-after-network/retry-220205/appium-4726.log \
  --log-timestamp
```

结果：`Appium REST http interface listener started on http://127.0.0.1:4726`。

### Trial 1: Feature Walkthrough

命令：

```bash
VW_APPIUM_SERVER_URL=http://127.0.0.1:4726 \
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/smoke/test_ios_feature_walkthrough.py::test_ios_feature_walkthrough' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/wda-recovery-after-network/retry-220205/allure-results \
  --clean-alluredir
```

结果：

- `1 passed, 1 warning in 155.61s`
- `01-prepare-home-session`: 3.7 秒

对比历史截图中的 25.9 秒，试点用例的显式 prepare step 已有明确下降。

说明：该用例内部可选入口 `wait-entry-floating-rental-mode-entry-car` 超时后按原逻辑 recover，pytest 最终仍通过。

### Trial 2: Search By Type

新增一个读用例试点后先做 collect：

```bash
.venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_search_by_type.py::test_user_can_filter_notes_by_type' --collect-only -q
```

结果：`1 test collected`。

真机命令：

```bash
VW_APPIUM_SERVER_URL=http://127.0.0.1:4726 \
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/message/test_ios_search_by_type.py::test_user_can_filter_notes_by_type' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/wda-recovery-after-network/retry-220205/search-by-type-allure-results \
  --clean-alluredir
```

结果：

- `1 passed, 1 warning in 93.48s`
- `01-prepare-home-session`: 3.8 秒

## Next Gate

### Message Rollout

在 `test_ios_search_by_type` 真机通过后，扩大到 message 读相关用例，仍不改发布笔记用例：

- `tests/message/test_ios_home_note_interactions.py`
- `tests/message/test_ios_message_browse.py`
- `tests/message/test_ios_search_by_type.py`
- `tests/message/test_ios_search_note.py`

本轮把显式 `prepare-home-session` 替换为 `ensure_read_session_on_home(...)`，并保留发布笔记路径不变。

补充修复：

- 首页判断增加详情加载失败 blocker，避免 `加载失败 / 详情加载失败` 覆盖层下，因底层缓存首页文本误判为首页。
- 首页笔记打开逻辑遇到详情加载失败时回退并尝试下一张卡片。
- iOS 分享按钮识别接受详情页顶部右侧分享图标。
- 评论用例改用短 ASCII 文本，避免中文九宫格输入偶发未输入。
- 底部点赞/收藏 action 在计数未变化时增加一次 element-center fallback。
- 系统消息页遇到 `通知加载失败 / Network Error / 重新加载` 时重试加载。

本地验证：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/message --collect-only -q
```

结果：`7 tests collected`。

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q -k 'home_visible or home_or_login_visible or ensure_read_session_on_home or ensure_logged_in_on_home'
```

结果：`22 passed, 37 deselected`。

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py -q -k 'open_system_message_page or like_note or favorite_note or tap_detail_share_button or bottom_action'
```

结果：`9 passed, 101 deselected`。

真机验证过程：

- 初始 6 个非发布 message 用例：`3 failed, 3 passed`，但所有 `01-prepare-home-session` 均约 `1.7-3.9s`。
- 修复详情加载失败与分享按钮后，单跑失败用例：`2 passed, 1 failed`，剩余为中文评论输入未落入输入框。
- 评论文本改短后单跑：`1 passed`，`01-prepare-home-session`: `3.9s`。
- 加入详情加载失败 blocker 后，`test_user_can_filter_notes_by_type` 从错误覆盖层起跑：`1 passed`，`01-prepare-home-session`: `3.8s`。
- 点赞 fallback 与系统消息 reload 修复后，6 个非发布 message 用例整组：

```text
6 passed, 1 warning in 916.69s
01-prepare-home-session: 3.7s, 3.8s, 3.9s, 4.0s, 4.0s, 3.7s
```

结论：message 非发布读用例已在真机证明 prepare 从历史约 20-26 秒降到约 4 秒以内，并且整组通过。

### Activity/Profile Expansion Attempt

在 message 范围通过后，继续小步扩展到非发布读路径：

- activity browse 中的筛选、搜索、详情、报名表读取、我的活动报名/点赞/收藏列表。
- profile 中 5 个查看型用例。

保持不变：

- 发布笔记测试。
- 发布活动测试。
- 发布入口 helper。
- 活动报名填写与提交付款页的完整 prepare。
- 草稿、租车下单、generated artifact。

为 activity 读路径补充的稳定性修复：

- activity feed/category 遇到 `加载失败 / 网络连接异常 / Network Error / 重新加载` 时自动点一次重新加载。
- home feed ready 判断把活动网络错误、地区/难度筛选覆盖层作为 blocker。
- activity detail route 解析接受真机页面上的 `ROUTE + 路线说明` 形态。
- 可报名活动和我的报名记录缺失时，对依赖环境测试数据的用例使用 skip，而不是硬失败。

本地验证：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/activity/test_ios_activity_browse.py apps/velowind-app/appium/tests/profile/test_ios_profile.py --collect-only -q
```

结果：`15 tests collected`。

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_browse_helpers.py -q -k 'activity_detail_snapshot or wait_for_activity_category_results or activity_feed'
```

结果：`12 passed, 28 deselected`。

activity 真机验证：

- 单跑 `test_user_can_filter_activities_by_cycling`：`1 passed`，`01-prepare-home-session`: `3.8s`。
- activity 读组首次运行：`4 passed, 4 failed`，失败集中在活动详情路线解析、无可报名活动、无我的报名记录。
- 修复路线解析与数据前置 skip 后，activity 文件重跑：
  - 前 3 个读用例通过，prepare 均 `3.7s`。
  - `test_user_can_open_activity_signup_form` 因当前环境没有可报名活动而 skip。
  - 随后 WebDriver session 被终止，后续用例在同一 pytest 进程中失败。

### Current WDA/Appium Blocker

activity 继续验证时 Appium/WDA 链路进入不可用状态：

- Appium server 仍监听 4726，但旧 session 已被终止。
- 新 pytest 进程创建 session 失败：`Unknown device or simulator UDID: '00008150-0006799C2693401C'`。
- `xcrun xctrace list devices` 能看到 `Zhigang的iPhone (26.2.1) (00008150-0006799C2693401C)` 在线。
- `xcrun devicectl device info details` 显示 `transportType: localNetwork`、`tunnelState: connected`。
- `system_profiler SPUSBDataType` 未看到 iPhone，说明当前不是 USB 可见链路。
- Appium log 显示：
  - `RemoteXPC devices listing unavailable`
  - `Tunnel registry at 127.0.0.1:42314 is not reachable`
  - `Please run the tunnel creation script first`
- 尝试运行：

```bash
appium driver run xcuitest tunnel-creation
```

结果：脚本要求 root/admin：`sudo appium driver run xcuitest "tunnel-creation"`。当前自动化环境不能交互 sudo，因此无法启动 tunnel。

当前结论：

- message 非发布范围已经真机完整通过，优化收益明确。
- activity 范围只完成部分真机验证，尚未完成 profile 和全量真机验证。
- 在 WDA 阻塞后，已校正 activity 边界：报名填写与提交付款页继续使用完整 `ensure_logged_in_on_home(...)`，筛选/搜索/详情/报名表读取/我的活动列表使用 `ensure_read_session_on_home(...)`；本地 collect 与相关单测通过。
- 继续真机验证前，需要把手机恢复为 Appium 可发现状态：优先用 USB 连接到 Mac、解锁手机并保持信任；或由人工用 sudo 启动 xcuitest RemoteXPC tunnel。

已满足第一轮 gate：

1. 真机单用例可以跑通。
2. `01-prepare-home-session` 相比历史约 20-26 秒有明确下降，并且用例通过。

本轮只新增一个读用例试点，没有继续批量替换。下一轮如继续扩大，应优先选择纯读路径，例如搜索和消息浏览；仍不改发布笔记、发布活动相关测试。

### Activity Browse Scoped Application

按 `activity/test_ios_activity_browse.py` 单文件范围继续应用优化，并重新收窄边界：

- 使用 `ensure_read_session_on_home(...)` 的读路径：
  - `test_user_can_filter_activities_by_cycling`
  - `test_user_can_search_activities_by_title_or_location`
  - `test_user_can_browse_activity_detail_fields`
  - `test_user_can_open_activity_signup_form`
  - `test_user_can_view_my_activity_signup_status`
  - `test_user_can_open_my_activity_signup_list`
  - `test_user_can_open_my_activity_liked_list`
  - `test_user_can_open_my_activity_favorite_list`
- 保持完整 `ensure_logged_in_on_home(...)` 的非纯读路径：
  - `test_user_can_fill_activity_signup_identity_fields`
  - `test_user_can_submit_activity_signup_to_payment_page`

这次没有改发布笔记、发布活动相关测试，也没有把优化扩展到其他文件。

本地验证：

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/activity/test_ios_activity_browse.py --collect-only -q
```

结果：`10 tests collected`。

```bash
.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_activity_browse_helpers.py -q -k 'activity_detail_snapshot or wait_for_activity_category_results or activity_feed'
```

结果：`12 passed, 28 deselected`。

真机验证：

先单跑最小读路径：

```bash
VW_APPIUM_SERVER_URL=http://127.0.0.1:4726 \
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  'apps/velowind-app/appium/tests/activity/test_ios_activity_browse.py::test_user_can_filter_activities_by_cycling' \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/activity-browse-scoped/filter-allure-results \
  --clean-alluredir
```

结果：`1 passed, 1 warning in 121.49s`，`01-prepare-home-session`: `3.8s`。

随后跑完整 activity browse 文件：

```bash
VW_APPIUM_SERVER_URL=http://127.0.0.1:4726 \
VW_IOS_TARGET=device \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_IOS_PLATFORM_VERSION=26.2.1 \
VW_IOS_DEVICE_NAME='Zhigang的iPhone' \
VW_IOS_XCODE_ORG_ID=K2VHBX5KLX \
VW_IOS_XCODE_SIGNING_ID='Apple Development' \
VW_IOS_UPDATED_WDA_BUNDLE_ID=com.velowind.rider.WebDriverAgentRunner \
VW_IOS_ALLOW_PROVISIONING_DEVICE_REGISTRATION=true \
VW_APPIUM_AUTO_OPEN_REPORT=false \
PYTHONPATH=apps/velowind-app/appium \
.venv/bin/python -m pytest \
  apps/velowind-app/appium/tests/activity/test_ios_activity_browse.py \
  -q -s --tb=short \
  --alluredir=.tmp/appium-ios/activity-browse-scoped/full-file-allure-results \
  --clean-alluredir
```

结果：`7 passed, 3 skipped, 1 warning in 1577.15s`。

读路径 prepare 耗时：

- `test_user_can_filter_activities_by_cycling`: `3.7s`
- `test_user_can_search_activities_by_title_or_location`: `3.7s`
- `test_user_can_browse_activity_detail_fields`: `3.8s`
- `test_user_can_open_activity_signup_form`: `3.8s`，因当前账号没有可报名活动 skip
- `test_user_can_view_my_activity_signup_status`: `1.7s`
- `test_user_can_open_my_activity_signup_list`: `3.8s`
- `test_user_can_open_my_activity_liked_list`: `3.8s`
- `test_user_can_open_my_activity_favorite_list`: `3.8s`

保留完整 prepare 的两个非纯读路径：

- `test_user_can_fill_activity_signup_identity_fields`: `26.5s`，因当前账号没有可报名活动 skip
- `test_user_can_submit_activity_signup_to_payment_page`: `19.9s`，因当前账号没有可报名活动 skip

结论：`activity/test_ios_activity_browse.py` 的读路径已经应用优化，并在真机上证明 `01-prepare-home-session` 从历史约 20-26 秒降到约 1.7-3.8 秒；非纯读的报名填写和提交付款页未套用快速读 session。
