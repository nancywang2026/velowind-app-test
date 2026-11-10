# 2026-11-07 AI 失败诊断与独立分支修复

## 范围与当前状态

- 用户要求：失败自动取证、AI 分类；仅修测试代码，每个问题创建新分支/worktree；产品问题建 Taiga Bug 并附相关截图；证据不足转人工；不自动合并。
- 用例 / suite：框架功能新增，定向验证 failure_triage、session_setup、timing_report、cleanup_report。
- 涉及模块：pytest 失败 hook、driver 设备锁、triage 队列/worker/Codex/修复保护/Taiga 适配器、配套 Skill。
- 实现分支：`codex/appium-ai-failure-triage`。保留原工作区 `.gitignore`、AGENTS.md、benchmarks、output、outputs 等既有改动。
- 当前状态：离线定向回归 108 passed；真机、真实 Codex 调用和真实 Taiga 建单未验证。
- 最后核实时间：2026-11-07，Asia/Shanghai。
- 历史参考：[会话冲突与清理边界](2026-09-15-ios-publish-cleanup.md)、修复记录索引。沿用“禁止抢占会话、passed 不等于清理成功”的约束，历史结果不作为本轮真机验证。

## 失败证据

- 功能缺口：既有 conftest 在 call/setup 失败时附截图/XML，但没有持久化 AI 任务、修复分支及 Bug 投递状态。
- 此次未以真实产品失败进行现场复现；使用临时 Git 仓库、合成 pytest 失败和本地 Taiga 替身验证。
- 真机相关证据缺失明确记为未验证，不创建演示 Bug 污染项目。

## 第 1 轮：实现与初始测试

### 分析和修改

- 增加 SQLite 队列和每次失败独立证据快照；pytest 不直接执行 AI。
- Codex CLI 只读结构化输出；框架创建分支、检查并应用最小补丁，独立单元测试与真机报告路径。
- 产品缺陷有草稿、截图审查/hash、Taiga 标签/运行标识/附件哈希去重和中断恢复。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_failure_triage.py
```

- 首次结果：3 passed / 6 failed；报告计时目录 `.tmp/appium-ios/runs/20261107-112750-63122/`。
- 已确认原因：INSERT 使用 8 个占位符，表有 7 列，导致入队失败；非产品/设备故障。
- 修正后：9 passed；增加覆盖后 14 passed，报告计时目录 `.tmp/appium-ios/runs/20261107-112859-63364/`。
- 真机：未执行。实际业务数据清理：未涉及；不能据此声称清理逻辑真机通过。

## 第 2 轮：相关框架回归

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_failure_triage.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py apps/velowind-app/appium/tests/unit-test/test_timing_report.py apps/velowind-app/appium/tests/unit-test/test_cleanup_report.py
```

- 首次结果：103 passed / 1 failed。
- 报告：`.tmp/appium-triage-implementation/verification-round2-failed.log`；计时目录 `.tmp/appium-ios/runs/20261107-113008-63568/`。
- 已确认原因：原测试要求 teardown 失败不取证；新功能明确要求采集 teardown 失败，因此更新该预期，并给截图添加 `-teardown` 标签，避免与 call 混淆。
- 不能把此失败覆盖成最初即通过；最终复验另记。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 限制 |
| --- | --- | --- |
| 模拟模型输出 + 真实临时 Git/pytest 子进程 | 验证框架动作和分支隔离 | 不证明真实模型诊断准确率 |
| 标签和附件内容哈希 | Taiga 投递中断后的显式恢复 | 不承诺跨机器原子建单或跨版本语义去重 |
| 更短的通用等待 | 不在本次自动修改范围 | 等待/阈值/异常处理改动一律交人工 |

## 遗留项与交接

- 配置实际 selector 对应的单元及受影响真机覆盖，明确可重跑的前置条件和副作用策略。
- 当前源码存在用户既有未提交改动；框架不会从 HEAD 自动修复 dirty 运行，避免源码版本错配。
- Taiga connector 读取项目时返回没有默认登录会话；未创建任何真实 Bug。独立 worker 需本地配置项目/API 与环境变量令牌，凭据不写入 Git/记录。
- 截图隐私/相关性审查仍需本地完成；没有合格证据时等待，不自动上传原图。模式脱敏和 AI 审查不是完整安全隔离。
- 进程检查见本轮工具输出：存在 4723 Appium 服务及历史 Allure 浏览服务；当时未发现其他真实 pytest 流程。本轮不创建、替换或结束真机会话。

## 第 3 轮：边界补齐与最终验证

- 补齐启动时源码快照与运行中漂移检测，防止基于错误 HEAD 修复。
- 同一问题新失败关联原任务；文档追加不会被当成中断的代码补丁。
- 两轮修复失败均保留补丁和日志，达到上限后停止；超时/Ctrl-C 仅终止本流程子进程组。
- 原始截图不交给模型；本地审查后的图片可作为 Codex 输入。模型进程只继承必要环境变量，不继承 Taiga token。
- 增加最后一页分页响应、本地 HTTP 适配器、原断言不可通过提前 return 绕过、源码漂移、两轮失败上限的验证。
- 最终命令：沿用第 2 轮四个定向测试文件。
- 实际结果：**108 passed, 1 warning in 20.01s**。warning 为既有 urllib3/LibreSSL 环境提示。
- 最终日志：`.tmp/appium-triage-implementation/verification-final.log`。
- 计时报告：`.tmp/appium-ios/runs/20261107-113650-64506/timing/`。
- Skill 格式校验通过；`git diff --check` 通过。
- Codex CLI 登录状态读取确认使用 ChatGPT 登录；未发起真实模型任务。
- 真机断言：未验证。真实业务数据清理：未验证。真实 Taiga 建单和附件：未验证。
- 完成项：失败入队、分支/worktree 修复与保护、受控验证、证据审查入口、Taiga 投递适配器、交接文档及配置示例。
- 下一步：提供 Taiga 项目并在本地配置令牌；建立实际用例覆盖/重跑策略；从干净代码版本进行真实模型和真机联调。没有启动长期 worker。

## 第 4 轮：绑定用户指定 Taiga 项目

- 用户提供：`https://project.velowind.com/taiga/project/velowind-app/issues?status=17`。
- 已将示例配置及本地 `.tmp/appium-triage-config.json` 绑定 `project_slug=velowind-app`、HTTPS API `/taiga/api/v1`，保留本地已有其他配置。
- 新增带认证的 slug→ID 解析，核对返回 slug，不写入推测的 ID。保留数字 ID 配置兼容。
- `status=17` 是列表筛选；没有证据说明它是新 Bug 初始状态，未写入创建状态。
- 现场：连接器登录返回会话，但项目列表为空，overview 返回解析错误；浏览器显示登录页，未认证 API 返回 401。没有取得项目 ID 或确认状态配置，未提交真实 Bug。
- 当前 shell 未设置 `VW_TRIAGE_TAIGA_TOKEN`，不读取或复制连接器内部凭据。后续在本机配置令牌后做认证查询与真实投递联调。
- 验证命令：`PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_failure_triage.py`。
- 专项结果：20 passed, 1 warning in 3.48s；报告 `.tmp/appium-triage-implementation/taiga-project-config.log`；本轮仅运行该文件，不称整套回归通过。
- 真机断言/真实清理/真实建单附件：均未验证。

## 第 5 轮：真机取证和真实 Codex 诊断联调

### 现场、范围与实际结果

- 用户明确允许真机验证。先检查 Appium / pytest，只有既有 4723 Appium 服务，无其他测试；复用配置中 Zhigang 的 iPhone（iPhone 17，iOS 26.2.1）。devicectl 确认有线 tunnel 已连接、开发者模式开启；xctrace 显示 offline 与 devicectl 不一致，后续实际 Appium 连接成功。
- 新增显式开关的只读探针 `tests/triage/test_ios_failure_triage_probe.py`，默认跳过。没有发布、下单、发消息或支付。第二例人为失败仅用于验证取证，禁止作为产品 Bug。
- 第一轮：1 passed / 1 intentional failed，30.25s；报告 `.tmp/appium-triage-live-20261107/`，任务 `bedb99adbc81443793c989b22ac00520`。
- 第一轮 PNG 约 99.79% 像素为黑色，XML 可读取活动列表与导航，截图不能确认产品界面正常。用户随后确认真机界面正常；不能将此认定为 App 黑屏。保留原图，不覆盖。
- 第一轮 `failed_step`、设备标识为空：确认 `pytest.fail()` 的异常类型不被 `except Exception` 捕获，且设备标识只读取环境变量。修正为同时捕获并重新抛出 pytest.fail 异常，设备标识回退实际加载配置。添加保持原异常对象的断言。
- 第二轮增加实际导航可见检查后：1 passed / 1 intentional failed，8.72s；报告 `.tmp/appium-triage-live-20261107-r2/`，任务 `1c60c4074c484ea3818f872ef5db3921`。PNG 正常展示活动页；PNG/XML 独立复制入队，步骤名与设备标识完整。
- Allure HTML 已生成：`.tmp/appium-triage-live-20261107-r2/allure-report/`。

### 真实模型失败、修正与边界

- 首次模型调用失败，只显示泛化错误；增加限长脱敏 stderr 后，重试确认服务端 401 / invalid_api_key。
- 本机 Codex 登录状态为 ChatGPT，但子进程继承 API Key 环境变量。默认改为 `agent_auth_mode=chatgpt`，不继承两种 API Key；保留显式 api_key 模式。不更改本机登录或任何凭据。
- 修正后真实 Codex 调用成功，分类 unknown/manual，指出 traceback 为主动 pytest.fail，无法据此建立产品/脚本缺陷。worker 转 needs_human，没有误报 Bug，也没有删除探针。
- 模型诊断中的不确定性仍保留（dirty 源码无法从 commit 还原、第一轮图片内容未提供模型等），不把受控探针的结果等同于一般诊断准确率。
- 增加 SQLite 逐次状态事件和追加式 handoff，避免恢复后覆盖先前失败；补充错误文本中 API Key 模式脱敏。旧调用的失败证据保留在本轮 worker 日志；不在记录中写凭据或认证响应。

### 验证命令与结果

```bash
# 真机，每轮使用独立 VW_APPIUM_RUN_ID、TRIAGE_DIR、ARTIFACT_DIR、TIMING_DIR 及报告目录
PYTHONPATH=apps/velowind-app/appium VW_APPIUM_TRIAGE_LIVE_PROBE=true .venv/bin/python -m pytest -q -s apps/velowind-app/appium/tests/triage/test_ios_failure_triage_probe.py
# 定向离线回归
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest -q apps/velowind-app/appium/tests/unit-test/test_failure_triage.py apps/velowind-app/appium/tests/unit-test/test_session_setup.py
```

- 实际完整命令参数与输出见 `.tmp/appium-triage-live-20261107/pytest.log`、第二轮同名日志、worker 日志和运行 metadata。两个探针都是真机运行；其中失败是预期人为触发，不能声称整套全绿。
- 定向离线最终结果：109 passed, 1 warning in 21.89s；`.tmp/appium-triage-live-20261107/unit-final.log`。既有 urllib3/LibreSSL 警告保留。
- 清理：探针没有新增业务数据，无对应业务清理操作；worker 的 cleanup=unknown 未被改写成 deleted。
- 自动修复分支→真机复验：未验证。当前工作区有用户已有和本轮未提交修改，仍遵守禁止从错误 HEAD 自动修复 dirty 运行的约束。
- 真实 Taiga 建单/附件：未验证，且不为人为探针创建演示 Bug。独立 worker 本地 Taiga 令牌仍未配置。
