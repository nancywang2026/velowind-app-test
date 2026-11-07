# 2026-10-27 使用 App 登录凭据识别环境并绑定清理账号

## 范围与当前状态

- 用户要求：使用不同环境账号密码登录 App，以成功登录确定环境，并使用成功的同一组凭据执行删除。
- 涉及模块：Appium 会话准备、密码登录、笔记 API 清理。
- 当前状态：已取消登录成功后的跨环境 API 核验，保留 VW_API_ENV 优先、App 拒绝后回退及同账号清理；本轮218项关联单元通过、原场次真机1 passed。此前笔记通过/删除记录保留；本轮场次未删除、整套 P1 未复跑；最后核实 2026-10-27。
- 历史参考：[入口修复](2026-10-27-ios-publish-entry-transition.md)、[生产清理配置](2026-10-27-note-cleanup-post-not-found.md)、[登录失败](2026-10-19-login-session.md)。历史通过依赖人工指定环境，没有自动识别。

## 原始证据与预期

- 之前 App 发布成功但默认 dev-api 删除返回 17210004；更正生产配置与凭据后完整目标 1 passed，新增笔记实际删除。
- 当前登录准备允许复用已登录态，不能据此证明当前配置凭据可登录；清理默认读取静态账号和 host，可能与 App 不一致。
- 新功能需执行真实 App 登录、识别失败与异常、保存会话匹配结果，删除严格使用匹配环境及账号。

## 第 1 轮：设计与实现

### 分析

- 自动识别显式启用，按配置顺序尝试每个环境一组凭据；先退出已有登录态；每组只提交一次，仅明确密码拒绝才切换下一组，超时/设备异常不当作环境不匹配。
- 登录后还需确认已认证个人页。相同账号密码跨环境可复用时不能唯一识别；预先拒绝重复凭据，并对成功凭据在配置的 API 环境做唯一性核验，异常或多环境成功时停止发布与删除。
- 匹配信息保存在 driver 会话，删除使用同一环境地址和凭据，不修改进程全局环境变量。默认关闭时保留旧配置行为。

### 修改与验证

- 实现及测试进行中，单元和真机均未验证。
- 清理：尚未产生本功能测试数据。

## 遗留项与交接

- 待实现、单元验证、真机登录候选切换及完整发布删除验证。
- 真机前检查进程，避免会话竞争；仅保存脱敏环境与结果，不保存凭据或完整认证响应。

### 第 1 轮阶段进度

- 已实现 `environment_login.py`：读取环境候选配置，退出已有会话，单次密码登录，确认已登录个人页，检查成功凭据在候选 API 中唯一匹配，结果缓存到 driver。
- `auth.py` 增加明确的 `LoginRejected` 类型、关闭重复提交的参数，登录恢复使用会话匹配凭据。
- `tests/conftest.py` 在创建 driver 后先识别环境，识别失败保存附件并退出会话；成功后在 Allure 环境中写入真实匹配环境和 API 地址。
- `message_detail.py` 发布时绑定当时识别结果；`cleanup.py` 使用绑定的环境和账号删除，登录信息变更时拒绝删除；`note_api_cleanup.py` 支持显式匹配地址，自动路径 API 附件隐藏密码和令牌。
- 默认未配置时保持原有流程。新增示例清单及 README；已创建 Git 忽略的 `.private/message-regression/app-environments.yaml`，顺序为 test → prod，引用已有本地测试/生产 YAML。生产私有配置已启用自动识别。
- 登录/环境识别/清理/会话回归 **222 passed / 17.89 秒**。更早阶段 **132 passed / 0.77 秒**，后续新增断言后才得到 222；不合并数量。消息/相册回归运行中。
- 首次 apply_patch 有一条空补丁校验失败，未修改文件；随后正确补丁已应用，不影响测试状态。
- 真机 `20261027-auto-environment-r1` 已启动，**未设置 VW_API_ENV**，并故意把静态 `VW_NOTE_CLEANUP_API_BASE_URL` 设为 dev-api，以核实识别结果能覆盖遗留静态 host。测试预期先拒绝 test 密码、再接受 prod 密码，最终删除仍使用 prod-api。该覆盖仅用于此次进程，未修改全局配置。
- 真机前检查无其他设备 pytest；当前运行中，尚不计通过，尚未创建本轮业务数据。

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_environment_login.py apps/velowind-app/appium/tests/unit-test/test_auth.py apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py apps/velowind-app/appium/tests/unit-test/test_config.py apps/velowind-app/appium/tests/unit-test/test_cleanup_config.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py -q
```

### 第 1 轮真机失败：安装包缺少设置按钮 ID

- `20261027-auto-environment-r1`：**1 setup error / 24.01 秒**，`Environment login could not identify the Me or login page`。尚未尝试账号登录、未发布、无新增清理目标。
- 失败截图与 XML 为 `artifacts/20261027-161447-app-session-setup.{png,xml}`。实际已在已登录“我的”页，存在 `me-page`，但没有本地新版源码中的 `me-settings-button`。不能把源码已有 ID 当成安装包也存在。
- 第一次查看失败图片时文件名取错，工具未打开；随后按实际目录文件名读取，不影响设备状态。
- 新增旧版个人页识别：必须在可见 me-page 内同时出现“我的笔记”“个人资料”；设置入口只在确认个人页后，按 XML 中右上角唯一 24–48pt 方形控件矩形点击，排除隐藏节点、正文和图标内部小节点。
- 现场独立调查已退出原 pytest 后才新建会话：按 (374,90) 点击成功打开设置抽屉，截图/XML 位于 `20261027-auto-environment-investigation/settings.*`。现场同时确认旧版退出按钮存在可见精确文字“退出登录”，没有新版按钮 ID，继续核对确认弹窗。
- 初始消息/相册完整单元回归 **307 passed / 60.92 秒**；新增旧版定位定向回归 **27 passed / 0.07 秒**。最终完整单元与真机结果仍待继续。

## 第 2 轮：兼容当前安装包的设置与退出确认

- 现场设置抽屉退出确认只有可见“温馨提示 / 您确定要退出登录吗？ / 取消 / 退出登录”，没有新版确认按钮 ID；附件 `20261027-auto-environment-investigation/logout-confirm.*`。
- 确认旧版个人页后使用 XML 派生的唯一右上按钮矩形；退出确认先验证弹窗出现，再点击可见的退出文本，避免设置抽屉后方隐藏同名按钮。确认后直接等待登录页，不在自动重定向期间再次点底部 Tab。
- 新增旧版个人页限制、隐藏父节点、正文位置排除及可见确认文本回归；环境识别定向 **28 passed / 0.07 秒**，完整关联回归进行中。
- 真机 `20261027-auto-environment-r2`：与 r1 相同命令条件（无 VW_API_ENV，静态清理地址故意设 dev-api），运行中。尚未计通过。

### 第 2 轮结果：已尝试 test 凭据，但内联错误不消失

- `20261027-auto-environment-r2`：**1 setup error / 83.46 秒**。已退出旧账号并提交 test 凭据一次，App 明确拒绝；随后等待旧错误自动消失无效，报 `Previous login rejection remained visible; refusing another attempt`。
- 现场 `artifacts/20261027-162053-app-session-setup.xml` 显示 `XCUIElementTypeStaticText name="密码错误"` 位于表单 y=437，为持续内联错误，不是定时消失的 toast。
- 尚未尝试 prod，本轮未发布、无新增笔记，无清理任务。保留失败，不将单元通过替代现场验证。
- 关联完整回归在本轮代码阶段 **227 passed / 17.89 秒**；当时未覆盖真实内联错误持续状态。

## 第 3 轮：每次明确拒绝后重新打开干净登录表单

- 下一组候选前重启 App（保留 App 数据与权限），重新进入未登录表单并确认旧“密码错误”已消失，再提交下一组。最后一组失败不再重启或额外尝试。
- 这样不把上一组持久错误误算到下一次请求，也不重复提交同一组密码；页面/设备异常仍停止，不归为凭据不匹配。
- 补充状态流回归：第一次拒绝留下内联错误、重新开表单清除旧错误、第二组成功；定向 **28 passed / 0.07 秒**。
- `20261027-auto-environment-r3` 使用原验证命令条件（未设置 VW_API_ENV，静态清理地址故意设 dev-api），当前运行中。

### 第 3 轮结果：真实 App 自动识别与绑定删除通过

- `20261027-auto-environment-r3`：**1 passed / 232.07 秒**；环境识别在 driver setup 执行，业务首页准备 0.9 秒、发布/图片内容校验 149.5 秒、API 清理 0.7 秒均 passed。
- 实际记录 `app-environment-login`：test → `app-rejected`；prod → `app-login-and-unique-api-match`。Allure 环境 `App Environment=prod`、`App API=https://prod-api.velowind.com/api/v1/mobile`。
- 本轮没有设置 `VW_API_ENV`，且静态 `VW_NOTE_CLEANUP_API_BASE_URL` 故意指向 dev-api；删除仍发往匹配的 prod-api，证明识别结果确实驱动清理，没有依赖手动生产 host。
- 当前发布 ID `pst-dfe46ff5418643a3a97f8ae1803b94b9`，唯一标题 `eacecaf8-测试 - 长白山真的有`。
- DELETE prod-api `/api/v1/mobile/posts/pst-dfe46ff5418643a3a97f8ae1803b94b9`：**HTTP 200 / code 0 / postId 匹配 / deleted=true**；traceId `a5d7072f-4913-41c9-ba5c-8d8d13b085f2`。
- `publish-note-cleanup-result` 为 deleted=[请求标题]、skipped=[]，没有 cleanup-pending；本轮新增笔记无清理遗留。
- 检查本轮 Allure 文本/json/xml 文件，候选密码原文匹配数 **0**。自动识别及匹配清理 API 的请求密码、响应 token 均脱敏。

### 最终代码补充与单元验证

- 支持不同手机号在其他环境不存在的情形：根据本地后端 `UserErrorCodes` 与中文资源确认 `10011001`（用户不存在）、`10011022`（未设置密码）、`10011023`（密码错误）均为确定的登录拒绝；账号禁用、限流、网络失败等不据此跳过环境。
- UI 精确识别可见错误文本，用户不存在文本仅返回通用原因，不传播其中账号标识；隐藏祖先下旧错误不参与判断。不同账号/未设置密码分支仅单元验证，当前真机使用同一手机号、环境密码不同的两组凭据。
- 发布页登录恢复也应用会话匹配凭据，避免基础配置为空或与匹配环境不同。
- 最终关联回归：**236 passed / 18.01 秒**，覆盖配置校验、真实退出流程适配、失败分类、唯一性、凭据缓存、清理地址/账号绑定、拒绝登录变更后删除、密码与 token 脱敏；既有 LibreSSL warning。
- 消息/相册完整集此前 **307 passed / 60.92 秒**；发布页恢复补充后定向 **3 passed / 230 deselected / 0.03 秒**。不同阶段及重叠测试集不合并计数。
- `git diff --check` 通过；真机会话已正常退出，未停止他人服务。

## 最终状态与使用

- 已完成：自动退出旧登录态、按候选尝试 App 登录、成功凭据的 API 环境唯一性确认、会话记录匹配结果、用同一环境/账号删除、Allure 脱敏结果、示例及 README。
- 当前本地 `ios-appium.prod.yaml` 已启用 `.private/message-regression/app-environments.yaml`，其中 test/prod 候选引用各自 YAML login。均使用 Git 忽略的私有配置，未把凭据写入记录或 Git。
- 其他运行可设置 `VW_APPIUM_ENVIRONMENT_ACCOUNTS` 指向候选清单；未设置环境识别配置时沿用原静态行为。每个 driver 会话只识别一次，不修改进程全局 host。
- 真机验证范围：当前 iOS 安装包的 test 拒绝、prod 成功及单条图片发布删除；UAT、Android、新版稳定设置 ID、不同手机号的实际登录未真机验证，整套未执行。
- 运行目录 `.tmp/appium-ios/runs/20261027-auto-environment-r3/`，Allure HTML 已生成至 `allure-report/`；保留 r1/r2 原 setup 失败附件与记录。

```bash
env -u VW_API_ENV -u VW_LOGIN_USERNAME -u VW_LOGIN_PASSWORD \
VW_APPIUM_CONFIG_FILE="$PWD/apps/velowind-app/appium/ios-appium.prod.yaml" \
VW_APPIUM_CLEANUP_CONFIG_FILE="$PWD/apps/velowind-app/appium/ios-appium.prod.yaml" \
VW_NOTE_CLEANUP_API_BASE_URL=https://dev-api.velowind.com \
VW_APPIUM_RUN_ID=20261027-auto-environment-r3 \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261027-auto-environment-r3/artifacts \
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
'apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]' \
-q -s --tb=short --alluredir=.tmp/appium-ios/runs/20261027-auto-environment-r3/allure-results
```

## 第 4 轮：VW_API_ENV 优先顺序及常规 pnpm 入口接入

### 新失败与原因边界

- 用户要求 `VW_API_ENV=prod` 优先尝试生产、`test` 优先测试；随后报告相同常规 pnpm suite 命令仍失败，并告知已放置 username/password。
- 新报告 run `20261027-162950-57363`，URL `http://127.0.0.1:63130/#suites/a315921332822b24a92de7455c3da80b/e62b98d7d4c3ff5a/`。报告共 **1 broken**，发布 passed、清理 DELETE dev-api 返回 HTTP 400 / 17210004。
- 保存的 publication ID `pst-6601bc8ea340408893f852fc22382590`，标题 `6388d869-测试 - 长白山真的有`，删除失败 traceId `f67497ff-2430-4dde-b31b-587c98e3c0fc`。
- 已确认：报告没有环境识别记录；用户命令未指定原先显式启用识别的生产 Appium 配置或候选清单，默认 ios-appium.yaml 也未配置识别。此前实现只覆盖显式开启的入口，常规入口遗漏。
- 当时运行的 VW_API_ENV / 静态 host 覆盖值未写入报告，因此不能仅根据用户贴出的命令判断 dev-api 是哪一项静态优先级导致；新增脱敏诊断用于消除该盲区。

### 修改

- `environment_login.py`：当存在默认私有清单且设置 VW_API_ENV 时，常规默认配置入口自动加载清单；显式清单和 Appium YAML 指定路径仍优先。
- 根据 VW_API_ENV 稳定重排候选：prod 先生产、test 先测试；首选拒绝后继续其余候选；未设置保留清单顺序；未配置或非法首选值在触碰设备前报错。最终环境仍由真实 App 登录及 API 唯一性决定。
- 新增 Allure `app-environment-login-order`，清理诊断增加优先变量、静态 host override 是否存在及会话匹配结果，不记录密码或认证响应。
- README 同步用户常规入口和优先级说明。

### 验证及实际清理

- 核对生产 YAML 中 login.username/password 均已填写；未使用原 JSON 中不同字段覆盖用户刚修改的 YAML。默认入口实际加载候选顺序为 `[prod, test]`。
- 使用本地生产配置中的账号对新失败唯一 ID 执行生产 DELETE，**HTTP 200 / code 0 / postId 匹配 / deleted=true**，traceId `8a98d676-a445-4814-808c-eea6ebf50d19`。原报告此次遗留笔记已实际删除；证据 `.tmp/appium-ios/runs/20261027-preferred-env-default-entry/recovery.json`。
- 首次合并环境/清理/runner 单元验证 **2 failed / 86 passed**：两项 runner 检查因 `ios-publish-all.yaml` 缺失及 ios-full 清单与断言不一致失败；runner 代码与这些清单本轮未修改，不能将该合并集记为全通过，也未为此改写用户 suite。
- 聚焦环境与清理回归 **77 passed / 0.16 秒**，覆盖 prod/test 首选成功、首选拒绝后回退、无额外配置变量时默认清单启用、未配置首选拒绝、未指定保持顺序。
- 真机前确认无其他设备 pytest。使用用户常规 pnpm / ios-p1 suite 入口，只增加 `-k test_user_can_publish_note_for_review` 定向验证报告失败项，未设置 VW_APPIUM_CONFIG_FILE / VW_APPIUM_CLEANUP_CONFIG_FILE / 显式候选路径。run `20261027-prod-priority-default-cli` 进行中，不提前计为通过；整套 P1 未复跑。

```bash
VW_API_ENV=prod \
VW_NOTE_CLEANUP_MODE=api \
VW_APPIUM_RETRY_FAILED=1 \
VW_APPIUM_PLATFORM=ios \
VW_APPIUM_SERVER_URL=http://127.0.0.1:4723 \
VW_IOS_UDID=00008150-0006799C2693401C \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios-device \
VW_APPIUM_RUN_ID=20261027-prod-priority-default-cli \
VW_ALLURE_OPEN_PORT=0 \
pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-p1.yaml -k test_user_can_publish_note_for_review
```

### 第 4 轮最终结果：用户常规入口生产优先通过

- `20261027-prod-priority-default-cli`：**1 passed / 12 deselected / 230.43 秒**，pnpm runner 退出码 0；本轮仅按 `-k` 复验原失败用例，不代表整个 P1 通过。
- 登录顺序附件：`preferred_environment=prod`，`candidate_order=[prod,test]`；首个 prod 凭据 App 登录成功，API 唯一性核验匹配 prod。
- 清理诊断实际记录 `VW_API_ENV=prod`、`static_api_override_present=False`、`matched_environment=prod`、`matched_api=https://prod-api.velowind.com/api/v1/mobile`。
- 发布/图片校验 148.7 秒 passed，清理 0.6 秒 passed；新 ID `pst-baef887593114ee7bd95ce83f107a0c5`（唯一标题 `a9b59732-测试 - 长白山真的有`）。
- prod-api DELETE 返回 **HTTP 200 / code 0 / postId 匹配 / deleted=true**，traceId `b65915f4-282f-4b1a-bf19-e5f4c11dd48a`。cleanup-result 为 deleted=[请求标题]、skipped=[]，无 cleanup-pending。
- 本轮新增笔记已实际删除；用户失败报告保存的旧 ID 也已在此前恢复步骤实际删除，两者分别核验，均无本轮已知遗留。
- Allure HTML 已由真实 pnpm runner 生成至 `.tmp/appium-ios/runs/20261027-prod-priority-default-cli/allure-report/`，原始结果同 run 的 `allure-results/`。
- 当前普通入口设置 `VW_API_ENV=prod` 即读取已存在的私有清单并优先生产，无需额外传生产 Appium 配置。`VW_API_ENV=test` 首选及回退在本轮单元覆盖；当前设备未切换为测试包，未声称 test 首选分支本轮真机验证。
- `git diff --check` 通过，设备 pytest 与会话正常退出。前述 2 项 suite 配置单元失败未改写或计为通过；整套 P1、UAT、Android 尚未在本轮执行。

## 第 5 轮：取消超出用户流程的跨环境 API 核验

### 失败证据与原因

- 场次复验 `20261027-activity-session-unpublished-r1`：1 setup error / 12 deselected / 102.29 秒；r2：1 setup error / 12 deselected / 101.36 秒。r2 报告 `http://127.0.0.1:52873/#suites/939591926e03527b1c0b544223c58491/8cf8cae6a4d49bb0/`。
- 两轮均为生产账号 App 登录成功、prod-api 登录 200 后，额外向 dev-api 提交同一凭据进行唯一性核验，未收到 HTTP 响应，报 `Cannot uniquely verify App environment: API login was inconclusive`。尚未执行场次步骤，无新增场次。
- 低层 urllib 同请求探测 timeout=8：8.06 秒后 read timeout。只确认客户端读超时，不推断服务端原因。无凭据或认证响应写入此记录。
- 用户询问“为什么要请求测试服”。重新核对原要求：VW_API_ENV 指定优先账号，App 能登录即确定环境，使用成功凭据执行删除。跨环境 API 唯一性核验是额外添加的约束，并非用户要求；使生产测试依赖测试 API 可用，不符合预期。

### 修改

- 移除 `environment_login.py::_verify_unique_api_environment` 及调用；App 单次登录成功且确认已认证个人页后立即绑定该候选，Allure result 改为 `app-login-matched`。不再为识别环境调用任何 API。
- 保留不同环境凭据校验、VW_API_ENV 优先级、仅明确拒绝才回退、异常停止、会话缓存及发布/清理账号绑定。清理仅向匹配 API 执行登录及目标删除，原删除断言保留。
- 单元删除过时的跨 API 唯一性要求，改为在成功/回退路径禁止网络访问，并核验匹配事件；README 同步当前规则。配置需使用能区分环境的账号密码。
- 本轮单元与完整场次真机结果待补；未将先前 setup error 改为通过。

### 第 5 轮验证进度

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_environment_login.py apps/velowind-app/appium/tests/unit-test/test_note_api_cleanup.py apps/velowind-app/appium/tests/unit-test/test_ios_p1_performance.py apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -q
```

- **218 passed / 19.08 秒**；`git diff --check` 通过。覆盖 prod/test 首选、明确拒绝回退、成功立即绑定且无 API 请求、同账号/地址清理及场次入口回归。既有 LibreSSL warning。
- 检查无其他 pytest/run_ios_tests 后，启动 `20261027-activity-session-unpublished-r3`。命令与场次记录第4轮相同，run/artifact ID 改 r3，增加 `--tb=short`；完整目标运行中，未提前计通过。没有启动竞争会话。

### 第 5 轮完整真机结果

- r3：**1 passed / 12 deselected / 451.50 秒**，runner 退出码0。生产优先，App 登录成功后记录 `app-login-matched` 及 prod API，不再执行跨环境 API 唯一性请求，已越过此前 setup 阻塞。
- 原场次用例完整执行：管理场次入口3.84秒、打开新增表单2.76秒；完整新增步骤371.3秒，成功信号“管理场次”。本轮只验证该目标，不代表 P1 整套通过。
- 报告 `.tmp/appium-ios/runs/20261027-activity-session-unpublished-r3/allure-report/`，原始结果同 run 的 `allure-results/`；临时 URL `http://127.0.0.1:54211/`。
- 清理单独说明：场次用例没有自动删除步骤，本轮“测试 - 场次 1027”未删除；本轮未执行笔记发布/删除，修改后真实笔记删除未重跑，仅相关单元覆盖。前轮笔记删除成功为历史结果。
- 设备会话正常 quit，检查 pytest/run_ios_tests 已结束，未停止其他服务。`git diff --check` 通过。
- 当前完成：按用户原规则识别环境、原失败场次入口及完整新增复验。未完成/未验证：新场次删除、整套 P1、Android、当前版本真实笔记删除。下一步如扩展验证，先检查设备占用，勿把本次单目标通过扩大为整套结论。

### 后续 Android 适配

- Android原视频用例环境识别失败另立 [Android登录准备记录](2026-10-27-android-environment-login.md)：已补个人页可见子节点、旧包设置/退出确认、协议框及提交前关闭键盘。真实 prod 登录准备已通过；联合235项单元通过。
- 当前完整视频目标出现1/2候选漏扫，已另补受控滚动；最终复验前真机离线，尚无整个Android目标通过结果。详见关联记录，未将iOS通过推广至Android。
