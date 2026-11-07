# 2026-09-15 iOS 活动场次入口失败

## 范围与当前状态

- 用户要求：分析并修复报告中的失败用例。
- 用例：`test_user_can_add_activity_session_from_my_approved_activity`。
- 模块：`velowind_appium/modules/activity_sessions.py`；iOS 真机。
- 当前状态：2026-10-27 已兼容通过+未发布入口，取消额外跨环境 API 核验后218项关联单元通过；原完整真机目标1 passed，整套未复跑，新场次未删除。历史各轮结论保留。
- 历史参考：`activity-session-ios-android-notes.md` 提到 iOS 部分控件需要 W3C touch；不能直接认定本次原因相同。

## 失败证据

- 原运行：`20260915-131118-69816`，目录 `.tmp/appium-ios/runs/20260915-131118-69816/allure-report`。
- 临时 URL：http://127.0.0.1:59938/#suites/939591926e03527b1c0b544223c58491/4ff131558541dc61/
- 步骤：`01-add-activity-session`；报错：`Unable to open Manage Sessions for an approved activity`。
- 附件副本：`.tmp/activity-session-fix/failure.png`、`failure.xml`。
- 截图处于“我的活动 / 发布”，底部“上海出发到杭州2”具有“通过、上架”状态和更多按钮。尚未进入新增场次表单。

## 第 1 轮：分析与验证

- 已确认：当前 `_ios_approved_more_point` 对失败 XML 返回 `(364.0, 780.5)`，位于可见目标按钮内；不能归因于没有合格活动。
- 推测：`mobile: tap` 没有触发菜单；通过同一真机会话对比 mobile tap 与 W3C touch 验证。
- 验证前检查 `ps -axo pid,etime,command`，无 pytest；存在多个常驻 Appium 服务，未终止任何进程。
- 验证命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python .tmp/activity-session-fix/probe.py`。
- 探针仅打开列表和菜单，不提交场次；运行中，结果待补充。
- 原用例断言：失败；实际清理：未涉及新增；修复后完整真机用例：未验证。

## 可复用方法与无效尝试

- 先用原报告 XML 验证定位坐标，再比较实际点击方式，避免盲目扩大超时。

## 遗留项与交接

- 待完成：点击对照、针对性修改和回归验证。

### 第 1 轮补充：排除点击失效

- 真机探针完成：找到 `(364, 542)`，`mobile: tap` 后 XML 出现“管理场次”。无需替换点击方式。
- 原运行 timing 文件：`timing/main-69817-1789449079120232000/timings.json`。末段每次 source 约 9.7–10.2 秒，tap-more 段仅约 0.006 秒（未执行设备点击），最后一次 scroll 2.35 秒后退出。与失败截图结合，确认最后滚动的结果未检查。

## 第 2 轮：滚动后检查与回归

- 修改 `_open_ios_manage_sessions`：每次滚动后必读一次新页面，即使滚动跨过截止时间；超时后不再滚动，菜单点击失败或详情恢复后也检查截止时间，避免无限循环。
- 保留同卡片“通过 + 上架”、可见范围校验及原错误断言，不改变活动状态。
- 新增边界回归：最后滚动跨截止时间后目标出现仍能点击；目标未出现时只补一次读取且失败退出。
- 真机探针未创建数据；完整新增场次用例回归已启动，运行 ID `20260915-activity-session-fix`。

### 验证命令与结果

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_ios_p1_performance.py apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -q
VW_APPIUM_RUN_ID=20260915-activity-session-fix VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/activity/test_manage_activity_session.py -q -s --alluredir=.tmp/appium-ios/runs/20260915-activity-session-fix/allure-results
```

- 单元：142 passed，18.64 秒；1 个现有 urllib3/LibreSSL 警告。`git diff --check` 通过。
- 真机：运行中；不能将单元通过计为真机通过。

### 第 2 轮实际结果（保留失败）

- 真机 `20260915-activity-session-fix`：1 failed，121.28 秒；仍是入口超时，未新增数据。
- 新失败 XML 中没有可见合格活动，只滚动到 9 月 6–8 日的待审活动。最后 source 8.96 秒，入口总耗时 93.44 秒。边界修改本身不足以解决长列表超过 90 秒的问题。

## 第 3 轮：独立查找预算

- 为 `add_activity_session` 增加可选 `manage_timeout`，默认保持原超时；该用例明确传 180 秒，只扩大活动列表查找预算，表单仍为 90 秒。
- 本轮将重跑完整真机用例；保留所有既有可见性和状态断言。
- 另发现用例仍断言固定 `2026-08-01`，而 draft 已使用当天加 15 天；另立记录修复过期断言，避免提交后误报。

### 第 3 轮单元结果

- API 改动后相关两个文件回归仍为 142 passed，18.61 秒。
- 补充默认/指定查找预算的参数化测试时，首次收集因缺少 `pytest` 导入失败；补上导入后 `-k prepares_home`：2 passed，111 deselected。未覆盖或隐去该中间失败。
- 真机回归命令同上一轮，run ID 与 alluredir 改为 `20260915-activity-session-fix-r3`。

### 第 3 轮实际结果与最终交接

- 真机：`20260915-activity-session-fix-r3`，**1 passed，441.19 秒**。入口 106.79 秒，提交 20.65 秒；场次发布检查流程 40.17 秒。106.79 秒实测证实原 90 秒预算不足。
- 报告目录：`.tmp/appium-ios/runs/20260915-activity-session-fix-r3/allure-results`；生成 HTML 位于同级 `allure-report`。
- 原始失败及第 2 轮失败均保留。完整相关单元 142 passed，新增预算参数测试补跑 2 passed；合计覆盖最终 143 个不同单元测试（未宣称最终一次全量运行 143 passed）。
- 数据清理：本用例无自动清理步骤，本轮新增“测试 - 场次 0915”未删除；未验证删除。前两轮入口失败未执行新增。
- 已完成：定位确认、最后滚动检查、独立 180 秒查找预算、日期断言修正、目标真机用例通过。
- 未完成/未验证：整套回归、Android 真机、测试场次删除。查找仍受固定 180 秒上限约束，列表进一步增长时可能再次超时，可另行研究限定测试活动/查询方式。
- 设备状态：本轮 pytest 已退出，会话正常 quit；未停止其他 Appium 服务。
- 下一步：如需整套结论，先检查设备占用后运行对应 suite；不要将此次单用例通过视为整套通过。

## 第 4 轮：2026-10-27 复发，活动通过但尚未发布

### 新失败证据

- 用户报告 `http://127.0.0.1:51511/#suites/939591926e03527b1c0b544223c58491/7f5965898c4c2a57/`，用例与原记录相同。
- 最新失败步骤 `01-add-activity-session`，**217.717 秒**，`Unable to open Manage Sessions for an approved activity`。运行目录待从报告服务进程核实。
- 失败附件 `allure-report/data/attachments/47fa1ce5ea8a3b1d.png`、`3aea2747cde5bf49.xml`；本轮调查副本 `/tmp/activity-session-20261027.{png,xml}`。
- 实际已滚到我的活动发布列表底部，唯一可见“通过”的测试活动为“测试 - 张家界大环线2天1晚”，状态“通过 + 未发布”；其他卡片为“被拒 + 上架”或“被拒”。
- 确认 `_ios_approved_more_point` 要求同卡片精确“通过 + 上架”，因此排除了现场唯一审核通过活动。本次不能复用历史“查找时间不足”结论或只扩大超时。
- 本地前端 `packages/activity/src/page/my-activities/Page.tsx::resolvePublishedRouteActions` 总是包含“管理场次”，上/下架操作另由 canToggleShelf 控制；安装包行为仍需现场核实。
- 进程检查无其他设备 pytest；未结束常驻 Appium/WDA。当前准备只打开通过但未发布的测试活动菜单，不提交数据。

### 修改与验证（进行中）

- 尚未修改筛选；先验证现场该卡片是否提供管理场次入口。保持审核通过要求，不选择被拒卡片，不改变活动上架/审核状态。
- 原用例未进入新增表单，无此次失败新增场次，无清理目标。

### 第 4 轮现场确认与修复

- 已核实原运行目录 `.tmp/appium-ios/runs/20261027-164911-75374/`。
- 独立只读交互探测：在同一生产 App 的“通过 + 未发布”测试活动上，点击 XML 派生 More 点 `(364,565)`，实际显示菜单“编辑 / 管理场次 / 上架活动”。现场截图和 XML `.tmp/appium-ios/runs/20261027-session-unpublished-investigation/menu.*`，未点“上架活动”、未创建场次。
- 当前 App 允许审核通过但未发布活动管理场次；历史“通过 + 上架”限制在本次安装包和数据状态下不再适合作为唯一入口条件。
- 修改 `_ios_approved_more_point`：保留通过状态及同卡片/可见/可点击/裁剪校验；优先通过+上架，找不到再使用通过+未发布；显式排除被拒、待审、审核中、下架。兼容旧 iOS 语义 More 分支的 shelf 条件。
- 用例验证说明同步为“审核通过且可管理场次（上架优先，兼容未发布）”，完整表单、日期和提交/发布流程未跳过。
- 新增回归：未发布可用、上架优先、不能跨卡片组合状态、即使有其他“通过”文本也拒绝被拒卡片；原隐藏祖先及屏幕裁剪覆盖继续保留。
- 关联单元 **147 passed / 18.80 秒**；完善被拒状态用例后定向 **10 passed / 24 deselected / 0.05 秒**。旧失败 XML 修复后可得到 `(364,528)`，落在现场通过未发布卡片 More 范围内。
- 原完整用例真机 run `20261027-activity-session-unpublished-r1` 已启动，使用 VW_API_ENV=prod 和常规 pnpm/ios-p1 入口，仅 -k 定向此用例。检查无其他设备 pytest 后才启动；本轮运行中，尚不计通过。
- 本轮新场次清理状态待核实。原用例没有自动清理步骤，不用 passed 代替实际清理。

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_ios_p1_performance.py apps/velowind-app/appium/tests/unit-test/test_activity_sessions.py -q

VW_API_ENV=prod VW_NOTE_CLEANUP_MODE=api VW_APPIUM_PLATFORM=ios \
VW_APPIUM_SERVER_URL=http://127.0.0.1:4723 VW_IOS_UDID=00008150-0006799C2693401C \
VW_APPIUM_ARTIFACT_DIR=.tmp/appium-ios/runs/20261027-activity-session-unpublished-r1/artifacts \
VW_APPIUM_RUN_ID=20261027-activity-session-unpublished-r1 VW_ALLURE_OPEN_PORT=0 \
pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-p1.yaml -k test_user_can_add_activity_session_from_my_approved_activity
```

### 第 4 轮完整复验首次结果：环境核验网络阻塞

- `20261027-activity-session-unpublished-r1`：**1 setup error / 12 deselected / 102.29 秒**。生产 App 登录成功、prod-api 密码登录 HTTP 200；dev-api 作为另一个环境的唯一性核验请求没有 HTTP 响应，记录 `network or invalid JSON response`，识别逻辑按原规则报 inconclusive。
- 该轮尚未执行 add-activity-session，不是筛选修复在现场失败，也不能计为通过；无新增场次、无清理目标。
- 保留环境识别对于网络异常停止的逻辑，不将无响应当成登录拒绝。下一轮在网络恢复后原样复验。

### 第 4 轮第二次结果及环境流程纠正

- r2 `20261027-activity-session-unpublished-r2`：**1 setup error / 12 deselected / 101.36 秒**。用户新报告端口 52873；仍是额外 dev-api 唯一性请求读超时，尚未进入场次步骤，无新增数据。原样重试未解决问题，保留失败。
- 用户追问后核对其要求，确定跨环境 API 核验为实现额外引入。已移除此依赖：指定环境账号 App 登录成功并确认已登录个人页后即绑定，只在明确拒绝时尝试其他账号。详见 [环境识别第5轮](2026-10-27-app-environment-login.md)。没有把超时当成账号拒绝。
- 场次定位和完整断言保持，准备再次使用常规 pnpm 入口复验。单元、真机和实际清理结果分别补充。

### 第 4 轮最终结果：原目标真机通过

- 联合环境/清理/场次单元 **218 passed / 19.08 秒**；没有替代真机结论。
- `20261027-activity-session-unpublished-r3`：**1 passed / 12 deselected / 451.50 秒**，pnpm 退出码0。命令沿用 r1，run/artifact ID 改 r3，额外 `--tb=short`。
- App prod 凭据成功即绑定生产，未再请求测试 API。活动发布列表6.86秒，管理场次入口3.84秒，新增表单2.76秒；完整新增步骤371.3秒，提交3.15秒，后续发布检查4.13秒，成功信号“管理场次”。本用例断言新增流程成功，不额外宣称已验证独立的上架业务状态。
- 报告目录 `.tmp/appium-ios/runs/20261027-activity-session-unpublished-r3/allure-report/`，原始结果同 run 的 `allure-results/`；临时 URL `http://127.0.0.1:54211/`。
- 实际清理：本用例没有自动删除场次步骤，本轮“测试 - 场次 1027”**未删除**；未用 passed 替代清理结论。r1/r2 均在 setup 失败，没有新增场次。
- 最终状态：原入口失败与完整目标已修复并真机通过；r1/r2 阻塞记录保留。整套 P1、Android、新场次删除均未验证。日期控件填写仍较慢，本轮不作为效率优化结论。
- 设备 pytest/run_ios_tests 已退出、driver.quit passed；未停止其他 Appium 或报告服务。`git diff --check` 通过。
- 下一步如需整套或清理验证，先检查现有进程，按精确场次目标核实后操作；不批量处理其他既有活动/场次。
