# Appium AI 失败诊断

pytest 采集失败并入队，由独立 worker 使用本机 Codex CLI 处理。非单元测试完成收集后，默认检查对应队列的 worker；未运行则自动后台启动，已有 worker 则复用。模型、修复和 Bug 分流仍在独立进程执行。支持 setup/call/teardown 失败；单元测试本身默认不入队。`show JOB_ID` 同时显示不可覆盖的 SQLite 状态历史，恢复任务不会抹去先前失败。

## 启动

从仓库根目录执行，复用已有 `.venv` 和已登录的 Codex CLI：

```bash
cp apps/velowind-app/appium/triage.example.json .tmp/appium-triage-config.json
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage list
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json once
# 持续处理新任务；Ctrl-C 停止，不会结束其他测试
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json watch
```

`--queue` 可指定队列目录，须与 pytest 的 `VW_APPIUM_TRIAGE_DIR` 一致。默认 `.tmp/appium-triage/`，其中 SQLite 保存状态，每个 job 有独立失败包、补丁、报告与 `handoff.md`。原截图会复制成独立快照，避免后续运行覆盖。不要把整个队列提交到 Git。

`VW_APPIUM_TRIAGE_ENABLED=false` 关闭入队。自动验证子进程强制关闭入队，避免递归修复。未配置 AI worker 时，原有测试仍照常运行。

## 测试失败但没有 AI 附件时

入队与模型处理是两个独立环节。pytest 默认自动检查并启动 worker，使用 `.tmp/appium-triage-config.json`，可用 `VW_APPIUM_TRIAGE_CONFIG` 指定其他配置。配置缺失或启动失败会输出具体提示。使用队列级进程生存期锁避免重复监听；旧进程退出后，下次运行测试会自动重新启动。没有系统登录自启或运行期间的持续进程保活。

`VW_APPIUM_TRIAGE_AUTOSTART=false` 只关闭自动启动，已有 worker 仍可消费队列；`VW_APPIUM_TRIAGE_ENABLED=false` 同时关闭入队和自动启动。单元测试、仅收集测试及自动修复验证子进程不会自动启动。正常运行示例：

```bash
VW_APPIUM_TRIAGE_ENABLED=true pnpm appium:ios:test:suite apps/velowind-app/appium/test-suites/ios-p1.yaml
```

检查原始 `allure-results/.triage-run-complete.json` 的 `triage_enabled`：为 false 表示当次运行关闭了入队，启动 worker 不会补回这次失败；测试结束后使用 `import-allure` 补导入。为 true 时再检查原用例是否有 `triageJobId`、CLI `list` 的状态和 worker 日志。`needs_human` 表示已诊断后转人工，与没有触发不同。旧 worker 启动日志不能证明进程仍活着。

## 自动修复范围和验证配置

第一版只支持已有 Python 自动化业务模块、已有单元测试文件的同路径文本修改。应用/后端代码、框架配置、断言修改、跳过、异常处理、等待/阈值调整、文件重命名/删除均转人工。静态检查加一次独立 AI 审查可拦截常见绕过，但不是任意代码语义正确性的证明，必须执行验证。

每个失败 selector 在本地配置中明确声明覆盖范围，例如：

```json
{
  "validation": {
    "apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]": {
      "unit": [
        "apps/velowind-app/appium/tests/unit-test/test_message_detail_helpers.py"
      ],
      "device": [
        "apps/velowind-app/appium/tests/message/test_ios_publish_note.py::test_user_can_publish_note_for_review[publish-note-changbaishan]"
      ],
      "safe_to_rerun": false
    }
  }
}
```

这是配置形状示例，不能直接证明这些选择器覆盖所有公共逻辑影响。发布、发消息、下单等变更数据的用例，需先确认可重跑前置状态、关联数据和清理策略，才将 `safe_to_rerun` 设为 true。默认 false 不执行真机重跑。公共模块修改时由维护者配置受影响用例列表，原失败 selector 必须在其中。

失败运行必须来自可还原的干净 commit。若存在未提交/未跟踪文件，保存 dirty 标记和差异摘要，但不把 HEAD 冒充实际运行源码，自动修复转人工。当前实现不保存可能含敏感信息的完整 dirty diff。

修复前创建 `codex/test-fix/<问题指纹>` 分支及独立 worktree，从失败 commit 开始。相同问题的新失败关联原任务，不重复覆盖补丁。最多两轮补丁；单元验证失败的补丁保存后仅反向撤销该轮修改，再提供失败日志尝试下一轮。中断时存在未验证补丁则转人工核对，不 reset 分支。不会自动 commit、push 或 merge。

真机验证使用新 worktree 的代码和独立报告目录。原解释器及本地环境变量复用；需要文件配置时请配置绝对路径，例如 `VW_APPIUM_CONFIG_FILE`，不要依赖新 worktree 中不存在的 `.private` 文件。已有 pytest/运行器活跃时等待；本仓库 driver fixture 使用平台级文件锁，不替换他人会话。第三方未使用此锁的 Appium 客户端仍需维护者协调。

单元/真机出现 skip、xfail、空执行或非零退出码均不算验证通过。断言结果、设备验证和清理状态分开；发现 `cleanup-result` 仅记为 `recorded_needs_review`，不把附件存在直接等同于清理成功。设备重跑中断不自动再执行，需先核对副作用。

## AI 的证据和边界

worker 在新测试会话开始时保存自动化 Python、测试数据 YAML、修复历史 Markdown 的脱敏源码快照与原始/脱敏 hash；失败时检测源码变化，关联原快照。单文件 1 MB、总快照 12 MB，遗漏文件明确记录。快照不包含根目录运行配置、私有配置或认证响应。dirty 运行可依据实际快照分析；现有自动修复仍要求可还原的干净 commit，不因新增诊断快照绕过修补与执行限制。旧 dirty 任务没有快照时明确显示源码不可还原，不读取当前 HEAD 冒充历史源码。

上下文从堆栈最内层开始，AST 提取完整失败函数、两层直接函数依赖、模块常量/导入，记录路径、行号、版本和 hash。超预算整项标记缺失，不按文件头截断。按测试和错误匹配 testdata YAML、历史索引及最多三篇相关历史正文；历史缺失时当前历史可作为明确标注的补充，不能作为运行源码。补证可继续请求具体函数、历史或 YAML。

XML 自动解析为保留父子关系、属性、坐标和选中状态的脱敏节点；丢弃未允许属性，敏感输入内容隐藏。较大 XML 优先保留目标/选中节点、祖先和相邻节点，明确记录遗漏数量和选择方法。模式与控件规则脱敏仍有局限，不应在异常/测试数据中保存认证响应或私密业务内容。截图须先完成本地相关性和隐私审查，哈希匹配后通过真实图像输入传入；未审查/不可读时明确标记 unavailable，不能声称已看图。已有 `review-evidence` 支持本地审查，诊断用历史截图不等于当前设备截图，也不直接授权 Bug 附件上传。

诊断协议 v2 输出候选原因、具体建议、结构化疑点（question / blocking / affects）和补证请求。worker 只接受本任务 XML/已审查图片、允许目录的源码函数/测试数据/历史，不运行模型命令、不操作设备、不读取任意日志或凭据。默认最多两轮补证、六项请求/轮、100000 字符上下文、600 秒诊断总时限；配置项 `max_evidence_rounds`（上限 4）、`context_chars`（上限 200000）、`diagnosis_timeout`（上限 1200）。重复请求、无新证据、越界或预算耗尽有明确停止原因。每轮上下文、实际 prompt、模型答案和证据处理状态保存在 job 的 `diagnosis-*` 目录，Allure 显示补证轮次、候选原因、修改建议和未解决项。

仅阻断疑点、缺乏依据或显式 manual 阻止自动分流；非阻断疑点保留但允许进入有依据的修补/审查。旧版字符串疑点按阻断处理，旧任务不会自动变成已验证。模型仍以只读模式运行、禁止调用工具，使用本机 Codex 登录；不加载用户 MCP 配置和业务令牌。补证由 worker 受控执行。

AI 超时、输出不合规、补证后仍存在阻断疑点时转 `needs_human`，但保留已确认事实、候选原因、建议和具体补证步骤。补丁和验证各有超时，子进程超时只结束本流程启动的进程组。队列状态在每次关键动作前落盘，重启后可查看或显式恢复：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage show JOB_ID
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json resume JOB_ID
# 增补了关键证据时重新诊断
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json resume JOB_ID --rediagnose
```

只做诊断回放并回写原报告，避免进入修补、真机重跑或建单：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json resume JOB_ID --rediagnose --diagnose-only
```

`diagnosed` 表示本次诊断已完成，不能等同于用例通过。已完成修复或建单任务不能重放。恢复不会重置两轮预算；运行中的任务应先确认所属进程已退出。

## 产品 Bug 和截图

产品缺陷先保存 `bug-draft.json`。要求预期、实际、步骤和证据齐全，且没有未解决的阻断疑点。截图需检查隐私和相关性；手机仍连接时，复用已有连接截取相关当前画面，不创建或替换 Appium 会话。worker 本身不新建取证会话；无法取得相关当前画面时保留 `waiting_evidence`。

完成本地审查后记录截图和设备状态：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage review-evidence JOB_ID \
  --png /absolute/path/to/reviewed.png --device-state connected_current_captured \
  --context /absolute/path/to/redacted-observations.txt
```

手机已断开时使用 `--device-state disconnected`，不得将历史截图说成当前画面。命令记录审查事实，不替你执行审查；PNG 校验、内容哈希和相关/隐私标记会在提交前再检查。连接设备的审查五分钟后过期，需重新截取。`--context` 可选，内容为经过审查的观察或 XML，不要求 JSON。

恢复任务后按本地配置提交。独立进程不能使用聊天中的 MCP 会话，因此实现 Taiga REST 适配器；聊天内手动处理仍优先使用 Taiga MCP。需要以下非敏感配置，令牌只从环境变量读取：

```json
{
  "taiga": {
    "api_url": "https://project.velowind.com/taiga/api/v1",
    "project_slug": "velowind-app",
    "token_env": "VW_TRIAGE_TAIGA_TOKEN"
  }
}
```

已按用户提供的项目链接配置 `velowind-app`。设置本机 `VW_TRIAGE_TAIGA_TOKEN` 后，会通过带认证的 `projects/by_slug` 查询解析项目 ID，并核对 slug；也支持直接填写已核实的 `project_id`。链接中的 `status=17` 只是列表筛选，不作为新 Bug 状态。

可显式设置项目的 `status`、`type`、`priority`、`severity` 数字 ID；否则交给服务端默认值。外部服务要求 HTTPS；测试可用 localhost HTTP。不跟随重定向或关闭证书验证。

按 `ai-triage-<指纹>` 标签查找未关闭 Bug，已有 Bug 追加本轮证据描述；相同运行不重复追加。附件使用运行标识及内容哈希去重。网络中断时保存 `bug_retry`，显式 resume 会先查远端状态，避免建单成功但附件失败后重复建单。指纹包含代码版本，跨版本/不同报错的相同业务问题仍可能需要人工合并；不承诺语义去重或跨机器原子建单。

## 当前验证边界

最终 108 项定向测试通过（含本功能 18 项测试）。离线测试覆盖真实 pytest 失败钩子、SQLite 状态、临时 Git 分支/worktree、真实单元验证子进程、模拟 Codex 可执行程序、Taiga 中断后附件补传及去重。不代替真实 Codex 调用、真机发布/清理或真实 Taiga 建单验证。

接入依据：[Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)、[Taiga REST API](https://docs.taiga.io/api.html)。配套规则位于仓库 `.agents/skills/appium-ai-triage/SKILL.md`。

## 真机链路探针

仅显式设置 `VW_APPIUM_TRIAGE_LIVE_PROBE=true` 时运行 `tests/triage/test_ios_failure_triage_probe.py`。第一例检查前台 App、原生上下文、屏幕尺寸和活动导航可见；第二例故意 `pytest.fail`，验证真实失败取证。因此验收预期是 **1 passed / 1 intentional failed**，不能把它当作产品缺陷或将断言删除以求全绿。默认收集会跳过这两例。

2026-11-07 实测详见修复记录：第二轮 PNG/XML、步骤名、设备标识入队成功；真实 Codex 已将故意失败识别为无法建立产品缺陷的人工处理项。它只验证取证和诊断分流，不代表真实缺陷自动修复、整套回归或 Taiga 建单验证完成。

## 在 Allure 中查看每次诊断

新运行的失败用例会带 `AI 诊断任务（等待 worker）` 附件。诊断完成后，在原用例的 Attachments 中查看 `AI 诊断结果 [状态]` 与 `AI 诊断结构化记录`。不同版本追加附件，原始 broken/failed 状态和截图不变。默认目录的既有 HTML 报告会自动刷新文件，浏览器按刷新查看；设置 `allure_refresh=false` 可关闭 HTML 重建，保留 raw 结果附件。

`once` 现在输出实际队列、待处理数量、Codex 调用阶段、终态及文件路径；空队列会明确提示没有调用 AI。CLI 与 pytest 都读取 `VW_APPIUM_TRIAGE_DIR`，显式 `--queue` 优先。其他 worker 持锁时会提示而不重复处理。

历史报告已经失败但未入队时，可在测试结束后补导入（只读原测试结果，不重跑用例）：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage import-allure /absolute/path/allure-results
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json once
```

导入按原 Allure UUID 去重，只采集异常消息与 PNG/XML，不读取 API 认证响应附件。历史源码无快照时不会自动修补。自定义 HTML 输出目录需通过 `import-allure ... --report /absolute/path/report` 指定；为避免替换非报告目录，自动 HTML 替换仅支持与 results 同父目录且名为 `allure-report` 的既有 Allure 报告。

若诊断完成但回写时 HTML 不可用，可单独重试报告更新，不重新运行模型或用例：

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.triage --config .tmp/appium-triage-config.json publish-allure JOB_ID
```
