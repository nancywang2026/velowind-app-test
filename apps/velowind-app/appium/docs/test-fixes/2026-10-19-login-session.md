# 2026-10-19 登录准备失败

## 范围与当前状态

- 用户要求：修复报告中的自动化脚本，让所有 case 通过。
- 当前状态：测试环境真机整套运行中；视频及图片发布/清理已通过，其他脚本兼容失败已分别记录并修复待复验。整套尚未通过。
- 用例：`tests/message/test_home_video_playback.py::test_four_home_videos_play_normally`，两份报告各只有这一条。
- 最后核实时间：2026-10-19。
- 历史参考：[模拟器视频筛选](2026-09-16-ios-simulator-video-discovery.md)、[视频数量](2026-09-20-home-video-count.md)。本次尚未进入视频验证，旧筛选问题不能作为登录失败原因。

## 失败证据

- 原运行：`20261019-150301-9038`、`20261019-151352-13637`，目录 `.tmp/appium-ios/runs/<run-id>/allure-report/`。
- 临时 URL：<http://127.0.0.1:62363/>、<http://127.0.0.1:51549/>。
- 两次均在 `logged_in_session` setup 中失败：`AssertionError: Login page remained visible after submitting credentials`。
- 平台为 simulator，iPhone 17 Pro Max / iOS 26.5，UDID `6C7DEC8B-93A0-447A-834E-180CF29F0C56`；报告 server 为 4725。
- 原报告没有失败截图/XML；当前报告钩子仅处理 call 阶段，setup 失败直接返回。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：现场 XML 存在可见 `XCUIElementTypeStaticText name="密码错误"`；App 已处理登录并返回凭据错误。不能把协议重复点击推测作为根因。
- 已确认：当前 4725 服务配置为 Android driver，当前服务状态不等同于原报告运行状态。
- 测试前检查未发现 pytest 运行；新建独立 4785 XCUITest 服务，未停止已有服务。
- 调查截图/XML 目录：`.tmp/login-fix-investigation/`。

### 修改

- `velowind_appium/auth.py`：识别当前页面可见、精确匹配的“密码错误”文本，直接报告登录被拒绝，停止无意义重试；不跳过登录或放宽视频断言。
- `tests/conftest.py`：setup 失败时也保存截图和 XML，避免登录准备错误没有现场附件；teardown 保持原有处理范围。
- 单元覆盖：密码错误停止重复提交、普通页面/隐藏错误/模糊文本不会误报、setup/call 失败附件和 setup 成功/teardown 行为。

### 验证

- 单元：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_auth.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q`；133 passed，17.46 秒；既有 LibreSSL warning。
- 修改前现场调查：实际调用 `ensure_logged_in_if_needed`，仍以旧超时错误失败；`.tmp/login-fix-investigation/live.xml` 已确认密码错误，`page.xml` / `page.png` 保留最终状态。
- 模拟器目标复跑：`20261019-login-diagnostic-fix`，40.29 秒，pytest 为 1 error（Allure failed），仍停于 setup。新报错明确为 `Login rejected: 密码错误`；没有进入视频验证。
- 实际复跑命令（使用现有配置中的凭据，没有在记录中写入）：

```bash
VW_IOS_TARGET=simulator VW_IOS_UDID=6C7DEC8B-93A0-447A-834E-180CF29F0C56 \
VW_IOS_DEVICE_NAME='iPhone 17 Pro Max' VW_IOS_NO_RESET=true \
VW_APPIUM_SERVER_URL=http://127.0.0.1:4785 VW_IOS_WDA_LOCAL_PORT=8185 \
VW_APPIUM_RUN_ID=20261019-login-diagnostic-fix \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261019-login-diagnostic-fix/artifacts \
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/message/test_home_video_playback.py -q -s --tb=short \
--alluredir=.tmp/appium-ios/runs/20261019-login-diagnostic-fix/allure-results
```

- 新报告：`.tmp/appium-ios/runs/20261019-login-diagnostic-fix/allure-report/`；已实际生成 HTML，并核对结果 JSON 中 PNG/XML 附件均存在。
- 附件原件：`artifacts/20261019-152102-test_four_home_videos_play_normally-setup.png` 及同名 `.xml`（上述 run 目录下）。
- `git diff --check` 通过。
- 真机：未验证。
- 清理：目前仅尝试登录，无新增业务数据。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 先核对 setup 与 call | 所有失败报告 | 本次失败发生在登录，视频断言尚未执行 |

## 第 2 轮：用户确认凭据，明确目标为测试环境

### 分析与现场证据

- 用户确认原密码、同一账号；本记录不写入凭据。不能仅因 UI 密码错误就认定用户提供的密码失效，必须核对环境。
- 模拟器安装包 Info.plist 为 1.2.4 / build 34；`main.jsbundle` 的域名检索只找到生产 API host，没有 UAT / test host。这支持当前模拟器包与目标环境不匹配的判断；未抓取 App 实际网络请求。
- 对已知生产登录接口使用当前配置单次预检：HTTP 400，业务码 10011023，Incorrect password；没有输出 token 或完整认证响应。
- 对已知 UAT 登录接口单次预检：HTTP 200，业务码 0，accessToken 存在；没有输出或保存 token。用户随后明确目标不是 UAT，而是测试环境，因此此结果不能算目标环境验证。
- 仓库历史测试地址为 `https://test-api.velowind.com`（`docs/test-reports/2026-07-15-xunfengji-app-bug-report.md`）；本轮严格 TLS 登录预检失败：`CERTIFICATE_VERIFY_FAILED: certificate has expired`，未绕过证书验证。
- 当前 `cleanup.yaml` 固定 UAT；尚未确认用户当前测试环境准确 host，未擅自修改为历史地址或安装 UAT 包。
- 输入调查：手机号输入比对一致；尝试切换密码可见性后未能证实明文与配置相同，因此不以此宣称密码输入校验通过。最终截图仍为密码错误；附件 `.tmp/login-fix-investigation/round2/page.{xml,png}`。

### 修改与验证

- 本轮尚无新增代码修改；上一轮 133 单元通过不等同于测试环境整套通过。
- 未执行发布、清理或整套；没有新增业务数据，没有安装或切换 App 环境。
- 已请求测试环境准确 API 地址或测试包位置；拿到地址后核实 TLS、登录、App 环境及清理 host，再继续回归。

## 遗留项与交接

- 用户已确认凭据、测试 host 和真机，接续本文件第 3 轮真机运行；本轮尚未新增业务数据。
- 本轮诊断修复有效，但没有解决凭据错误，不能标记用例或整套通过。测试 driver 已正常退出；停止本轮创建的 4785 服务，其他 Appium 服务保持原状态。
- 不将登录成功、单用例通过、模拟器通过或清理完成互相替代。

## 第 3 轮：切换用户更新的测试环境真机

- 用户明确更新的是连接的 iPhone 真机，而非原报告中的模拟器；测试环境 host 明确为 `https://dev-api.velowind.com`。
- 真机 UDID `00008150-0006799C2693401C`；devicectl 核实当前 App 1.3.0 / build 64。
- 模拟器补充运行 `20261019-test-env-home-video` 仍是旧包，40.85 秒、1 setup error，密码错误；保留此失败，不将它记为已验证新包。
- 已核查进程，仅本轮模拟器 pytest，完成并退出后再启动真机；未停止其他 Appium 服务。
- 真机运行 `20261019-device-test-home-video`：`VW_IOS_TARGET=device`、`VW_IOS_NO_RESET=true`、独立 Appium 4785、`VW_API_ENV=test`，本轮首次运行另显式指定 dev-api 清理地址。
- 真机登录准备通过；`01-prepare-home-session` passed（1.5 秒）；`02-verify-2-home-videos` 运行中。完整目标、整套和清理结果待补。
- 环境配置修复与单元结果独立记录：[测试环境 API Host](2026-10-19-test-api-environment.md)。
- 后续整套 `20261019-device-test-full-r1`：视频、基础遍历、4 个底部 Tab、笔记分类、笔记搜索、图片发布及新增活动场次均 passed，当前累计 10 passed / 6 failed，后续报名等仍运行中。
- 新增场次步骤 267.1 秒通过；实际新增场次未清理，不能用 passed 代替清理成功。图片笔记 dev-api 登录和删除均 HTTP 200，无本轮笔记清理遗留。
- 6 条原失败分别对应草稿导航、朋友圈面板判断、系统通知更名、两条首页 Button 卡片、活动行程加号；修复细节和每次验证见对应独立记录，尚需本轮结束后真机复验。
- 首轮最终结果：12 passed、10 failed、2 skipped、1 setup error，共 25 项，2183.97 秒；Allure HTML 已生成在该 run 的 `allure-report/`。保留所有失败，不将中途 50→80→60 快照配置的诊断轮次计为最终回归。
- 新增问题分别记录：活动快照深度、活动分类“全部”、搜索测试数据、实际租车门店；80 深度候选触发 WDA 错误后已撤回，默认改为现场可读取卡片的 60。

## 第 4 轮：统一配置整套复验

- 运行 `20261019-device-test-full-r2`；日志 `.tmp/appium-ios/device-test-full-r2.log`；产物 `.tmp/appium-ios/runs/20261019-device-test-full-r2/`。
- 配置：真实 iPhone 17 / App 1.3.0 build 64，`VW_API_ENV=test`（dev-api），独立 Appium 4785，`VW_IOS_NO_RESET=true`，默认快照深度 60；按 `ios-full.yaml` 所有方法完整运行，`--maxfail=0`。
- 开始前确认第一轮及门店调查会话均已结束，无其他 pytest 竞争设备。
- 本轮结果、清理和遗留项待完成后补充。
- 最终修改版本合并单元：12 个受影响测试文件，644 passed / 5 deselected，57.61 秒；排除项是分享记录中 HEAD 基线同样失败的 5 个旧发布 mock，未修复或掩盖它们。完整控制台日志 `.tmp/appium-ios/unit-final.log`。
