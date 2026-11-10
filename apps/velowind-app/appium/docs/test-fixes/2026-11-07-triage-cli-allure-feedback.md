# 2026-11-07 AI 诊断终端反馈与 Allure 关联

## 范围与当前状态

- 用户反馈：运行 `triage once` 无反馈；要求每次诊断结果直接显示在 Allure。
- 分支：沿用功能实现分支 `codex/appium-ai-failure-triage`，不提交或合并用户已有改动。
- 模块：triage CLI、worker、pytest 采集插件、新增 allure_results 关联/导入/回写模块。
- 状态：120 项相关回归通过；实际失败的真实诊断、Allure 回写、既有 HTTP 报告刷新已验证。
- 最后核实时间：2026-11-07，Asia/Shanghai。
- 历史参考：[AI 框架与真机联调记录](2026-11-07-ai-failure-triage.md)。沿用保留原失败、分离清理状态、不抢占真机会话的约束。

## 失败证据

- 默认队列 `.tmp/appium-triage` 返回 `[]`，后台 worker PID 70283 空闲且日志没有内容。
- 旧 `once` 只执行 `worker.tick()`，未输出任务数量、开始/结束、空队列提示；已确认这是命令静默的直接原因。
- 现有 Allure `.tmp/appium-ios/runs/20261107-130629-70682` 包含 1 个 broken 发布用例，错误消息 `NoteCleanupApiError: Note cleanup POST failed: HTTP 400`，但默认队列无对应任务。
- 该次漏入队原因尚未确认；不能说已被 worker 消费，因为队列会保留处理后的记录。用户终端的环境变量和旧进程加载情况无法从当前 shell 反推。
- 原记录 UUID `fb95a3b5-127d-4e02-939a-64babe2ccc87`。本轮不重跑发布，不重复生成笔记，不修改断言或业务清理。

## 第 1 轮：修改与离线验证

### 已确认分析与修改

- CLI 输出实际队列路径、空队列提示、任务数量、模型调用进度、终态/原因和结果路径；watch 空闲不每轮刷屏。
- CLI 默认队列也读取 `VW_APPIUM_TRIAGE_DIR`，与 pytest 一致；忙锁明确提示其他 worker 正在处理，不重复调用模型。
- 采集端将实际 `--alluredir`、报告路径写入任务，在 Allure 用例加入 triageJobId 标签和排队附件。结束标记保证后台回写等待测试落盘。
- worker 将每版诊断作为文本/JSON 附件回写确切的原结果；版本内容哈希防重复，后续诊断追加附件保留旧版本。原 status、断言、时间、截图不改变。
- 已有默认 Allure HTML 报告从原结果重新生成，临时目录完成后替换；已有浏览器页面需刷新。自定义报告输出路径保留 raw 结果并提示手动刷新。
- 增加 `import-allure` 显式导入已完成报告的 failed/broken 结果，按 UUID 去重；历史源码不能还原时明确 dirty/unknown，不从当前 HEAD 自动修复。
- 增加 `publish-allure JOB_ID` 仅回写报告，不重新调用 AI、不重跑测试。
- 停止本会话自己启动、已确认空闲的 worker 加载新代码；未停止 Appium 或用户测试。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_triage_allure_results.py apps/velowind-app/appium/tests/unit-test/test_failure_triage.py
```

- 结果：28 passed, 1 warning in 4.72s。
- 日志：`.tmp/appium-triage-allure-integration/unit.log`。
- 验证包括真实合成 pytest→Allure 标签关联、结束标记、精确匹配、防错误附件路径、导入幂等、逐版诊断保留、原 broken 状态保留、空队列输出、忙锁不重复调用 AI。
- 未执行新的真机用例；真实发布断言及清理结果不在本轮验证范围。

## 第 2 轮：既有实际失败的诊断与报告回写

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage import-allure .tmp/appium-ios/runs/20261107-130629-70682/allure-results
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json once
```

- 实际导入 1 条任务 `30e8ee4d544c4db0a741e6bc29466a1e`；不是重跑发布用例。
- CLI 已实时显示队列、任务 ID、选择器和“正在调用 Codex”状态；终态和 HTML 验证另行追加。

## 无效尝试与限制

| 方法 | 结果 / 适用边界 |
| --- | --- |
| 对空队列直接执行旧 once | 静默退出，用户无法区分无任务与处理成功；已补显式输出 |
| 只查看 Allure broken 状态就推断已触发 AI | 不成立，必须有队列记录或诊断附件 |
| 从历史失败直接套用当前 HEAD 修复 | 不允许；历史源码/环境不完整时标记人工处理 |

## 遗留与交接

- 诊断结果不改变原测试失败，更不能把 cleanup 失败改成清理成功。
- 真实 Taiga 建单与真实自动修复分支闭环仍未验证；不为这次报告功能验证创建演示 Bug。
- 默认队列为空的历史原因未确认，新增启动/入队日志和 Allure 完成标记用于后续定位。

### 第 2 轮实际完成结果

- Codex 真实诊断完成：unknown / manual，任务 needs_human。保留其证据不足结论，不伪造清理成功或完整根因。
- 原用例已追加 `AI 诊断结果 [needs_human]`、`AI 诊断结构化记录`，Allure HTML 重建完成。
- 经既有服务 HTTP 实际读取 `http://127.0.0.1:55112/data/test-cases/4037d02ca60f2029.json`，确认两项 AI 附件已经对外展示，status 仍为 broken。
- Allure summary 仍为 total=1、broken=1；没有将原失败改成通过。
- 再次执行 once 明确打印“没有待自动处理任务”“needs_human: 1”“0 个任务”，未重新调用模型。
- 完整相关回归：120 passed, 1 warning in 23.16s。文件包括 test_triage_allure_results、test_failure_triage、test_session_setup、test_timing_report、test_cleanup_report。
- 日志：`.tmp/appium-triage-allure-integration/verification.log`；计时报告 `.tmp/appium-ios/runs/20261107-132048-72095/timing/`。
- `git diff --check` 通过。没有新增真机业务操作，原失败清理问题未在本轮修复或复验。
- 已重新启动本会话的 watch 加载新代码；既有 Appium 和用户 Allure 服务未被结束。新日志 `.tmp/appium-triage/worker-watch.log`。


## 第 3 轮：2026-11-09 再次未触发诊断

### 失败证据与已确认原因

- 运行 `20261109-172411-94838`，报告 `.tmp/appium-ios/runs/20261109-172411-94838/allure-report/`，HTTP `http://127.0.0.1:63805/`，用例 UID `8b382180ac08218b`。
- `.triage-run-complete.json` 明确为 `exitstatus=1, triage_enabled=false`；原结果无 triageJobId 或排队附件。默认队列仅有 11 月 7 日历史任务，本次未入队。
- 现场无 triage worker 进程；旧 worker-watch.log 最后为 11 月 7 日的启动信息。旧进程为何退出、原 pytest 环境由谁关闭，当前证据不能确认。
- pytest 插件默认入队；runner 继承调用环境且不会自动启动独立 worker。自动修复验证子进程关闭入队是防递归设计，不能从此推断本次来自自动修复。
- 原业务失败为发布后的 API 清理登录 POST HTTP 400；发布步骤 passed，清理失败，整套受 maxfail=1 提前结束，不能称整套通过。

### 操作与验证（进行中）

- 检查进程后未创建或替换 Appium 会话、未重跑发布、未停止现有 Appium / Allure 服务。
- 执行 `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage import-allure .tmp/appium-ios/runs/20261109-172411-94838/allure-results`，导入任务 `feac3a689dea44bd861d2c25e10cc5b9`。
- 执行 `PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json once`，已开始真实 Codex 诊断，等待结果。
- 本轮未改测试逻辑；单元测试未执行。真机重跑未执行；业务清理仍失败/未解决。
- 下一步：核实模型终态及原 HTTP 报告附件，恢复当前机器的监听。后续测试需确保 `VW_APPIUM_TRIAGE_ENABLED=true`；启动监听不会更改已运行/其他终端的环境变量，也不保证重启后自启。


### 第 3 轮诊断与回写完成

- 任务 `feac3a689dea44bd861d2c25e10cc5b9` 真实 Codex 诊断完成，unknown / manual，终态 needs_human；不足以确定清理 HTTP 400 根因。没有自动重跑或修复业务。
- AI 诊断结果及结构化记录均已回写并重建报告。重建后原 UI UID 改为 `db90afd56fe32919`，旧 `/data/test-cases/8b382180ac08218b.json` 返回 404；重新枚举报告后 HTTP 验证新用例两项附件存在，status 仍 broken。可从原服务 suites 重新打开用例。
- 第一次 HTTP 核对因沿用旧 UID 失败，随后按新 UID 核对成功；失败核对未启动监听进程（脚本在此前退出）。后续通过正式 ensure_worker 启动并核实持有队列监听锁。

## 第 4 轮：按用户要求在测试前自动启动 worker

### 修改

- 用户明确要求“如果 AI worker 没有启动就先自动启动”。
- 新增 `triage/startup.py`，pytest 完成收集、开始执行测试前检查对应队列的 watch 生存期锁；未运行时脱离测试进程后台启动，已有 worker 则复用。
- CLI watch 持有队列级生存期锁，多个并发启动仅允许一个监听；进程退出后内核释放锁，下次测试可重新启动。原 worker 逐任务锁继续防止 once/watch 重复模型调用。
- 默认使用 `.tmp/appium-triage-config.json`，支持 `VW_APPIUM_TRIAGE_CONFIG`。配置缺失、启动未就绪、异常明确打印；日志在队列 worker-watch.log。没有新增凭据或系统自启服务。
- 单元测试、collect-only、关闭入队和自动修复验证子进程不启动；`VW_APPIUM_TRIAGE_AUTOSTART=false` 可只关闭自动启动。合成失败框架测试显式关闭 autostart，防止触发真实模型。

### 验证

- 命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_triage_startup.py apps/velowind-app/appium/tests/unit-test/test_failure_triage.py apps/velowind-app/appium/tests/unit-test/test_triage_allure_results.py`。
- 首轮 32 passed, 3.19s；补充 collect-only 边界后最终 **32 passed, 1 warning in 4.77s**，报告 `.tmp/appium-ios/runs/20261109-173537-97307/`。
- 真实空队列子进程验证启动、复用、终止本测试创建的进程、重新启动；未结束他人任务。hook 单测验证禁用开关、单元/仅收集跳过、配置与队列传递。
- 实际默认队列 ensure_worker 输出“已自动启动”，随后核对进程/锁；使用本地既有配置。没有再次模型调用已完成诊断。
- 本轮未新增真机操作；原清理仍失败，真机完整复验未执行。不会把自动监听启动等同于原业务缺陷修复。

### 遗留与边界

- 当前机器监听已恢复；以后非单元测试启动会检查并补启动。没有系统重启自启、运行中 watchdog，worker 运行途中退出则下次启动测试恢复。
- 本次报告明确 triage_enabled=false；自动启动遵守显式禁用，不会覆盖其他终端环境。正常运行应移除关闭开关或设为 true。
- 配置 prod 选择缺失另见共用环境配置记录第 2 轮；与本问题分开记录。


## 第 5 轮：2026-11-10 Android 选图报告仍需人工查看（只读诊断）

- 报告 HTTP `http://127.0.0.1:49750/`，用例 UID `49b02b3717c3599d`，job `dbd7b2fadb324223a792def855aa0d02`；运行目录 `.tmp/appium-android/runs/20261110-120049-19391/`。
- HTTP 读取原用例、诊断文本和结构化附件，确认 worker 已完成诊断，结论 unknown/manual，原因 `Diagnosis has unresolved evidence/uncertainty`；不是未启动或未入队。
- 本轮读取队列原 PNG/XML：前台 `com.android.photopicker`，影集 selected=true，仅见“相机”“屏幕截图”，未见“长白山”，选择计数 0/100。已进入选择器，不能继续把“相册未打开”作为同等可能。最终快照不能单独证明完整滚动过程、素材索引或权限状态。
- 与 2026-11-05 指定影集记录现象一致；该历史正文含本机 DEX、配置、日志与独立相册入口核查，但不能据此声称本次系统配置已重新核验。
- 当前 context builder 只取堆栈文件、索引和配置文件列表，按文件头 `content[:30000]` 截取，仅允许 py/md；不能覆盖文件后部选图函数、直接依赖 photo_picker 和 YAML 用例。诊断明确报告这些缺项。
- PNG/XML 仅作为 evidence_paths；缺 reviewed-evidence/reviewed-context 时截图不作为图像输入、XML 内容不进入上下文。agent 禁止工具和额外文件读取；当前 schema 无补证请求字段，worker 无补证循环。
- worker 在 uncertainties 非空、evidence 为空或 decision=manual 时直接 needs_human，不区分阻断/非阻断疑点。dirty_hash 存在不能替代实际运行源码快照；当前默认 context 从 commit 读取源码。
- 实际临时 prompt 未持久化，以上输入范围依据当前实现、队列记录和模型明确反馈交叉核对，不把当前重建上下文当作原始请求。
- 本轮仅分析并追加记录，未修改诊断框架、未重新调用 AI、未重跑真机或发布/清理；原 failed 和 needs_human 保留。下一步需实现函数级上下文、相关历史和用例数据、经审查附件输入、受控补证及按阻断项分流，再进行历史样例回放。
