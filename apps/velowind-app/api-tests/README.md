# 私聊后端自动化

将 Postman「私聊测试：3条未读、5条消息、置顶隐藏、笔记活动分享」的 23 个请求实现为独立 Python API 模块与顺序流程。无需 Appium、设备或测试桥接服务；沿用仓库 Python 3.9+ 和 pytest。报告统一使用 Allure，依赖仓库已有的 `allure-pytest`。独立安装可执行 `.venv/bin/python -m pip install -r apps/velowind-app/api-tests/requirements.txt`。

## 测试数据与替换

所有可替换业务数据在 `data/private_chat.example.json`：服务地址、A/B/C 账号、笔记/活动 ID、文案、发送数量、未读预期和执行参数。复制成 `data/private_chat.local.json` 后修改，不需要改 Python。

- 可以直接填写 JSON 值，也可以使用 `${变量名}`。变量依次从 `--environment` 指定的 Postman 环境导出和操作系统环境读取，操作系统环境优先；禁用变量不读取。
- 使用原集合的 `base_url`、`phone_a/password_a`、B/C 对应变量、`post_id`、`activity_id`。不使用导出中的旧 token、userId 或 `retry_request_id`；每次重新登录、生成独立 UUID。账号可额外配置 `expected_user_id` 验证身份。
- 真实账号文件放在 `*.local.json` 或仓库 `.tmp/`，不要提交；示例和契约快照不含凭据。Postman 导出可能只包含共享值，执行前必须检查配置。掩码值不能用于登录。
- `to_b.count`、`to_c.count` 控制发送数量；更改 B 数量时一起更新未读预期。`unread_b = baseline_unread_b + unread_delta_b`，增量须等于 B 发送数量。默认基线为 0、最终 3。`preparation.mark_b_history_read=true` 时，若B与A已有未读，先以B身份仅将该会话历史标记已读，再重新查询确认基线0；false或未配置时保留严格前置检查。不会删除历史消息或处理其他会话。
- `post_id` 是已有可分享笔记 ID；`activity_id` 是活动 ID，不是场次或报名 ID。A 满足实名认证门禁，B/C 允许接收 A 私信；仅 A 关注 B 不一定满足互关限制。
- 文案支持 `{run_id}`，批量文本另支持 `{index}`、`{count}`。每轮运行唯一标识与消息 UUID 自动生成，方便追踪，不属于固定测试数据。

## 快捷命令

在仓库根目录执行：

```bash
pnpm api:private-chat:check   # 只检查独立数据文件，不发送请求
pnpm api:private-chat         # 执行真实私信用例，结束后自动生成并打开 Allure
pnpm api:private-chat:report  # 生成并打开 Allure HTML
pnpm api:private-chat:unit    # 离线验证脚本，不访问真实后端
```

默认数据文件为 `data/private_chat.local.json`（相对本 API 工程）；更换文件可执行 `pnpm api:private-chat --data /绝对路径/其他数据.json`，Postman 环境可追加 `--environment /绝对路径/环境.json`。配置检查的 Allure 输出单独存放，不混入业务结果。用例成功或失败都会自动生成并打开报告，测试退出码保持失败状态；report 命令用于之后重新打开。配置检查和离线测试不会自动打开浏览器。

## 控制台日志

快捷命令默认实时输出时间戳、步骤开始/通过/失败、API方法与路径、HTTP/业务状态码及耗时、文本发送进度、未读计数、发送间隔等待和最终报告位置。立即flush，不等整套结束再输出；不打印账号密码、token或请求/响应正文（正文在脱敏Allure附件中）。直接用pytest运行想看实时输出时追加 `-s`。

## Allure 报告运行入口

在仓库根目录运行（默认读取你已填写的独立数据文件）：

```bash
PYTHONPATH=apps/velowind-app/api-tests .venv/bin/python -m velowind_api \
  --data apps/velowind-app/api-tests/data/private_chat.local.json \
  --alluredir .tmp/private-chat-api/allure-results --open-report
```

不论用例成功、断言失败还是配置阻断，均生成 Allure result。`--open-report` 会在非配置检查模式下生成HTML并启动浏览器；可用 `--report-dir` 指定HTML目录，默认是results目录旁的allure-report。浏览服务后台运行，输出位于HTML目录的viewer.log。未安装Allure CLI或生成失败时保留原始结果并在控制台提示，不掩盖用例失败。手动重新查看报告：

```bash
allure generate .tmp/private-chat-api/allure-results -o .tmp/private-chat-api/allure-report --clean
allure open .tmp/private-chat-api/allure-report
```

结果目录采用 UUID 文件追加，不删除旧结果；单轮隔离时给 `--alluredir` 指定新的目录。`generate --clean` 仅重建 HTML 报告，不清除 result 原始记录。CLI 的 `--report` JSON 作为辅助脱敏附件来源保留，不再作为主要报告入口。

Allure 展示业务步骤与耗时、断言失败原因、未读基线和实际值、清理状态。每个业务步骤下包含 API 子步骤及独立 request/response JSON 附件：请求方法、URL、headers、query、body；响应状态码、headers 和完整 JSON 正文。HTTP 错误正文及非 JSON 响应同样保留；网络故障明确标识未收到响应。密码、手机号、Authorization、token、cookie 等先脱敏再写入文件。仅新运行能够记录正文，旧记录无法补回未采集的 request/response。业务断言失败为 failed，配置/接口/网络异常为 broken；配置检查使用单独用例名称，不能算业务用例通过。通过 pytest 运行时使用原生 Allure steps 和附件，加 `--alluredir` 即可。

## 其他执行方式

在仓库根目录执行离线验证：

```bash
.venv/bin/python -m pytest -c apps/velowind-app/api-tests/pytest.ini apps/velowind-app/api-tests/tests -m 'not live' -q
```

配置检查不会发送请求，缺值退出码为 2：

```bash
PYTHONPATH=apps/velowind-app/api-tests .venv/bin/python -m velowind_api \
  --data apps/velowind-app/api-tests/data/private_chat.local.json \
  --environment .tmp/g1-private-chat.postman_environment.json \
  --check-config --report .tmp/private-chat-api/config-check.json
```

真实执行会发送 8 条文本及 2 条分享，改变关注、置顶、隐藏状态；使用专用测试账号，串行运行，B 不要在其他设备打开与 A 的聊天页。移除 `--check-config` 即运行完整流程；建议每轮使用新的报告文件名，保留失败证据。成功退出 0，接口或断言失败退出 1，缺配置退出 2。

也可通过 pytest 集成 CI（未配置时显式 skipped）：

```bash
VW_API_DATA=apps/velowind-app/api-tests/data/private_chat.local.json \
VW_API_ENVIRONMENT=.tmp/g1-private-chat.postman_environment.json \
VW_API_REPORT=.tmp/private-chat-api/live-report.json \
.venv/bin/python -m pytest -c apps/velowind-app/api-tests/pytest.ini \
  apps/velowind-app/api-tests/tests/test_live.py -v --alluredir=.tmp/private-chat-api/allure-results
```

报告保存分步状态、请求方法/路由、请求 UUID、HTTP/业务状态、耗时、消息 ID 和未读结果，请求体和响应正文均以脱敏附件保存，不保存明文密码和 token。网络超时不会自动重发写请求；报告标记结果可能未知，先按请求 UUID 查服务端再处理。

## 模块与覆盖

| 模块 | 可复用能力 |
| --- | --- |
| `config.py` | 外置 JSON、Postman 变量解析、前置校验 |
| `http.py` | HTTP/业务双层校验、超时、拒绝重定向、请求日志 |
| `auth.py` / `follows.py` | 手机密码登录、身份核对、关注 |
| `messages.py` | 独立文本发送、clientMessageId 与请求 UUID 一致 |
| `conversations.py` | 列表、置顶、隐藏 |
| `sharing.py` | POST 笔记、ACTIVITY 活动分享，区分 bizType 规则 |
| `history.py` / `checks.py` | 历史分页/恢复、消息/卡片/未读/排序断言 |
| `scenario.py` | 按原集合顺序组合功能，遇错终止后续步骤 |

自动断言覆盖：三身份不同、关注成功；B 未读基线/总数/增量；8 条文本唯一 ID 和接收侧正文/发送人/接收人/会话（入站clientMessageId应为空，发送端仍核对该字段）；C 置顶且置顶分区在前（不假设 C 必须排第一）；A 隐藏后列表无 B 且 B 视角未读不变；两张分享卡片发送及接收侧类型/业务 ID；最终 C 仍置顶且最新摘要为活动卡片。隐藏检查在再次分享前完成，不凭分享后的状态倒推隐藏是否成功。

`data/postman-contract.json` 是 2026-09-18 从实际 Postman 导出的 23 请求精简快照（含导出 SHA-256）。离线测试核对全部请求覆盖；在原流程上额外增加 1 次 B 列表查询验证隐藏仅作用于 A。

源码核对范围：`/Users/test/github/velowind-backend-service` 的 `MobileMessageCenterController`、`PrivateMessageApplicationService`、消息/会话 DTO、`MobileUserFollowController`。此路径只用于开发时核对，运行不依赖该目录。部署环境仍须实测。

## 复跑准备与发送节奏

独立数据文件中的可替换设置：

```json
{
  "preparation": {"mark_b_history_read": true},
  "execution": {"send_interval_seconds": 21}
}
```

这是需合并进完整配置的片段。当前local/example已启用：先清除B对A的历史未读，再严格验证本轮3条未读。报告保留 initial_unread_b、preparation.marked_read_count、baseline_unread_b，已读状态改变与消息清理分别记录。

发送间隔作用于同一流程中所有文本和分享；距上次发送完成至少21秒。后端源码默认发送者每分钟5条、同一会话每分钟3条，完整10条发送通常需约3–4分钟。`request_interval_seconds`仍控制普通请求间隔。限流规则可能随部署变化；小时/天额度、其他客户端并发发送仍可能导致失败，脚本不会关闭限流或自动重发。复跑不改变基线0、总数3和增量3的断言。

## 分页、清理和验证边界

后端首次历史读取为最新页，最大 50 条；`afterMessageId` 向后取增量，不支持向前翻旧历史。脚本按 `hasMore` 继续，限制页数和游标循环；遇到一次 `resyncRequired` 用返回快照替换旧页，重复恢复报失败。任何目标未找到、字段缺失或重复消息均失败，不将截断结果作为通过。数据校验要求单批文本加分享能放入首个历史窗口；并发外部消息仍可能挤出目标，报告应作为失败调查。

配置开启历史已读准备时，仅在发送前按需调用一次B对A会话的 `read`；发送开始后不调用已读接口，始终不调用 `read-all/clear`，不自动删除历史或取消已有关注。测试断言通过不代表清理完成；实际写入后报告 `cleanup=not_performed`，失败/超时也可能留下数据。本次没有可靠的仅删除本轮消息并恢复全部原状态的清理实现；复测需维护专用测试数据或更换账号。

离线 HTTP 契约测试仅证明脚本行为，不证明已部署后端通过；API 接收记录不证明 App 推送、红点或卡片 UI 通过。现场进度见 `VALIDATION.md`。
