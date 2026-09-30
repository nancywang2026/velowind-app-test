# 2026-09-20 发布笔记 API 清理登录失败

## 范围与当前状态

- 用例：`test_user_can_publish_note_for_review[publish-note-changbaishan]`，iOS 真机，API 清理模式。
- 当前状态：已确认生产 App 的 API 清理错误访问 UAT；已支持运行时环境选择（默认 UAT），生产真机目标用例通过且本轮笔记实际删除成功。最后核实：2026-09-20。
- 历史参考：[发布与清理记录](2026-09-15-ios-publish-cleanup.md)。本次发生于 API 登录，不是历史 UI 删除定位问题。

## 失败证据

- 报告：[用例详情](http://127.0.0.1:50130/#suites/a315921332822b24a92de7455c3da80b/19f565b55e60425a/)。
- 目录：`.tmp/appium-ios/runs/20260920-101213-38173/allure-report/`。
- 发布步骤 passed，清理步骤 broken；登录 POST `/auth/login/phone/password` 返回 HTTP 400，业务码 `10011023`，`Incorrect password` / `mobile.auth.password.incorrect`。
- 脱敏 API 附件：`data/attachments/77b84efab5a15ea9.txt`；发布身份附件：`data/attachments/6052c1d768fbaecf.txt`。
- 本次笔记 ID：`pst-2ec00f0a42c448cdae72e47dbfca5e7f`。删除请求尚未发出，实际清理未完成。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：后端拒绝登录密码，与用户先前反馈密码已修改一致。App 已登录会话可以发布，但 API 清理独立使用配置凭据登录。
- 配置优先级：`VW_LOGIN_PASSWORD` 高于 YAML 的 `login.password`；默认文件 `apps/velowind-app/appium/ios-appium.yaml`，可由 `VW_APPIUM_CONFIG_FILE` 覆盖。
- 尚未确认新密码所在配置来源；未猜测或重试旧密码。

### 修改

- 仅添加诊断记录与索引，未改删除逻辑、凭据或断言。
- 无失败修改尝试。

### 验证

- 已读取本地报告 JSON、API 响应附件及配置加载代码。
- 单元测试：未执行，无逻辑改动。
- 真机复测：未执行；未创建设备会话、未检查设备占用。
- 清理结果：本次报告未删除成功，当前远端状态未重新查询。

## 可复用方法与无效尝试

- 区分登录 POST 失败与删除 DELETE 失败；修复登录后仍需独立验证删除结果。
- 报告历史另有 DELETE HTTP 400，不作为本次密码失败已覆盖解决的结论。

## 遗留项与交接

- 更新实际启动环境中的密码或确认新密码已保存的本地配置路径，再验证 API 清理及残留笔记。
- 真机复跑前先检查 Appium / pytest 进程，避免抢占会话。
- 不在记录中保存账号密码、令牌或完整认证响应。

## 第 2 轮：增强 Allure 请求响应展示

- 用户明确要求展示登录用户名和密码，以及删除 API 的 request / response。
- 已确认原逻辑将请求响应合并到 API 子步骤的 `api-call` 附件，密码脱敏；本次报告登录失败，未发出 DELETE，因此不存在删除响应。
- 修改 `note_api_cleanup.py`：保留合并附件，增加独立 `API request` 与 `API response` 附件；登录请求体按用户要求记录实际用户名和密码，token / cookie 继续脱敏。报告文件会持久化明文登录密码；本修复记录不保存实际凭据。
- 所有实际发出的登录和删除请求均经过此逻辑，HTTP 失败也生成附件；未执行请求不伪造响应。
- 验证命令：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py -q`。
- 结果：24 passed，0.05 秒；既有 urllib3 / LibreSSL 警告。覆盖用户名密码展示、token 脱敏、请求响应拆分和 HTTP 失败附件。
- 运行目录：`.tmp/appium-ios/runs/20260920-102943-45859/`；无新真机 Allure 报告。
- 真机和实际清理未重新验证，旧报告不变；需要重新运行用例生成新附件。无失败修改尝试，未创建或替换设备会话。

## 第 3 轮：新报告仍然登录失败

- 用户提供新报告：<http://127.0.0.1:54106/#suites/a315921332822b24a92de7455c3da80b/78fb16ec1926b7c8/>。
- 运行目录：`.tmp/appium-ios/runs/20260920-103609-49484/allure-report/`。
- 发布步骤 passed；清理登录 POST 返回 HTTP 400、业务码 10011023、Incorrect password；未执行 DELETE。
- 新附件已生效：`API request` 为 `69a07831353b82c0.txt`，`API response` 为 `39785f5d7d41ce84.txt`，合并附件为 `c6a88d8febcc2143.txt`。
- 仅比较值而不输出凭据：本次报告发送的用户名、密码均与当前 ios-appium.yaml、android-appium.yaml 的 login 配置一致。当前诊断 shell 未设置 VW_LOGIN_PASSWORD；不据此推断原测试进程环境。
- 已确认当前配置中的凭据被服务端拒绝；增加日志不解决密码失效。尚无有效替代凭据，不猜测、不重复登录。
- 本次遗留笔记：`pst-688f7bebde704d2fbac39ea654ad6870`，报告未删除成功，远端当前状态未另查。
- 本轮无代码修改、无单元或真机复跑、无新增设备会话；待用户更新有效 UAT 凭据后验证登录和删除。

## 第 4 轮：按要求准备真机复测，登录预检仍被拒绝

- 用户授权修复后直接真机验证直到目标用例通过。
- 先比较当前 iOS YAML 与第 3 轮报告：密码尚未变化；使用当前配置对 UAT 登录接口做一次真实预检，仍返回 HTTP 400 / 10011023 / Incorrect password，未获得 token。
- 预检通过仓库虚拟环境直接调用 `_request_data`，诊断只输出 HTTP 状态、业务码和消息，未保存或输出密码及认证响应。
- 检查进程：发现 3 个 Appium 服务（PID 10100、12850、93466），未发现 pytest / run_ios_tests；未结束他人进程，未创建新设备会话。
- 对照 API 测试登录实现，清理使用相同 phone/password 请求结构，没有证据支持修改请求格式解决错误。
- 当前阻塞：缺少服务端接受的 UAT 密码。已请求用户更新本地 login.password 或提供现有有效配置路径；不猜测密码，不改成跳过清理或绕过 API 来制造通过。
- 本轮无代码修改、未运行单元、未启动真机发布用例；实际删除仍未完成。获得有效配置后先复查登录，再检查设备占用并运行目标真机用例，检查删除响应与 cleanup-result。

## 第 5 轮：用户确认真机为生产环境，修复硬编码 UAT

- 用户明确说明当前 App 运行生产环境。此前 Incorrect password 仅证明 UAT 拒绝该凭据，不能证明生产密码错误；前几轮关于凭据的推断范围在此纠正。
- 已确认代码缺陷：清理登录和删除均硬编码 UAT，与用户确认的 App 环境不一致。
- 修改：cleanup_config.py 增加 note_cleanup_api_base_url()；读取环境变量 VW_NOTE_CLEANUP_API_BASE_URL，优先于 cleanup.yaml 的 cleanup.note_cleanup_api_base_url。支持 HTTPS origin 或 /api/v1/mobile 基础路径，拒绝空值、嵌入凭据、查询参数及非法路径。
- note_api_cleanup.py 登录与删除共用配置地址，不再隐式回退到 UAT；cleanup.yaml 暂留空等待准确生产地址。
- 当前仓库未找到可确认的生产 API 地址，已询问用户；未猜测域名后发送凭据。
- 验证：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py -q`，36 passed，0.09 秒。
- 运行目录：`.tmp/appium-ios/runs/20260920-104528-53932/`。真机未复跑，实际清理未完成；用户已授权拿到地址后继续真机验证，无需再次审批。

## 第 6 轮：生产地址确认、环境配置与真机验证进行中

- 用户确认 UAT host 为 https://uat-api.velowind.com，生产 host 为 https://prod-api.velowind.com；运行时指定环境，未指定默认 UAT。
- 增加 VW_UAT_API_HOST / VW_PROD_API_HOST，默认使用用户给定 host；VW_API_ENV=uat|prod 选择，缺省 uat。保留显式基础地址覆盖以兼容上一轮配置。
- 当前 YAML 不固定生产环境；本次复测显式设置 VW_API_ENV=prod。
- 生产登录预检 HTTP 200、code=0、获得 accessToken；未输出或记录完整认证响应。确认同一配置在生产可登录，此前 UAT 密码错误由环境不匹配触发。
- 单元 39 passed（0.10 秒），运行 `.tmp/appium-ios/runs/20260920-104853-54998/`；覆盖默认 UAT、两个 host、环境变量选择及覆盖、非法配置与 API 合同。
- 真机前未发现其他 pytest/runner，Appium 4723 ready；sessions 查询不受支持（HTTP 错误），未据此声称不存在会话。
- 启动真机运行 `20260920-prod-cleanup-fix`：设备 00008150-0006799C2693401C，目标图片发布用例；结果待完成，不提前标通过。

```bash
VW_API_ENV=prod VW_IOS_TARGET=device VW_APPIUM_RUN_ID=20260920-prod-cleanup-fix VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20260920-prod-cleanup-fix/artifacts VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest 'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' -q --alluredir=.tmp/appium-ios/runs/20260920-prod-cleanup-fix/allure-results
```

### 第 6 轮最终结果

- 真机运行 `20260920-prod-cleanup-fix`：**1 passed，159.62 秒**，目标用例本体 152.69 秒。仅此目标图片发布用例，整套未验证。
- 登录：生产 `/auth/login/phone/password`，HTTP 200 / code 0。
- 删除：生产 `/posts/pst-095b0fd627be4559a236f0e08a9cd135`，HTTP 200 / code 0，响应 postId 匹配且 deleted=true。
- `publish-note-cleanup-result` 明确 deleted 为目标标题、skipped=[]；本轮无 cleanup-pending。API request/response 独立附件已存在。
- 报告目录：`.tmp/appium-ios/runs/20260920-prod-cleanup-fix/allure-report/`；原始结果同运行目录下 `allure-results/`；控制台日志 `pytest.log`。
- 单元 39 passed，`git diff --check` 通过。未修改用户账号密码，未绕过清理断言。
- 原历史失败轮次的两条已记录遗留笔记未在本轮额外删除；本轮删除结论仅针对上述新发布 postId。
- 已完成用户要求的目标用例生产真机验证。后续运行示例：`VW_API_ENV=prod pnpm appium:ios:test:profile publish`；不指定 VW_API_ENV 默认 UAT。host 可用 VW_UAT_API_HOST、VW_PROD_API_HOST 分别覆盖。

- 新报告临时入口：<http://127.0.0.1:56290/>（本地报告服务存续期间有效）。
