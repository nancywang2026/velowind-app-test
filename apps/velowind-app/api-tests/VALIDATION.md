# 验证记录：2026-09-18

分支：`codex/private-chat-api-automation`。仅新增 `apps/velowind-app/api-tests/`，保留工作区原有未提交文件；未修改 Appium 流程和后端。

## 来源与现场

成功从 Postman 导出目标集合，共 23 个请求；读取请求正文、认证、前置脚本与检查脚本。原集合多项业务判断只记录变量或要求人工检查，新增实现使用显式断言。保留脱敏精简契约供覆盖核对。

用户指定真实环境为「G1 三用户测试环境（请填写）」。实际导出位于仓库 `.tmp/g1-private-chat.postman_environment.json`，权限 0600；关键配置导出值为空。Postman 界面有本地服务地址及资源值，账号密码显示为掩码，本地值没有完整包含在导出中。窗口工具多次报 ScreenCaptureKit -3812，重连后能短暂访问但无法稳定取得完整可执行数据。没有用掩码、旧 token 或其他环境替代。

## 验证轮次

1. 首轮 pytest 收集失败：Python 3.9 的 HTTPError 对象在 pytest 自动生成参数 ID 时触发 `KeyError: file`。给参数设置显式 ID 后解除，未涉及业务代码。
2. 第二轮：26 passed、6 failed、1 skipped。测试用本地 HTTP 服务错误地对 `Content-Length: 0` 调用 JSON 解析，导致无正文 pin/hide 请求连接断开。修正夹具为空请求体处理；生产客户端正确地将此类断连视为写入结果未知，未重试。
3. 第三轮：32 passed、1 skipped，覆盖完整本地 HTTP 流程、错误未读/置顶/隐藏/卡片/接收人/消息缺失、游标循环/恢复/上限、网络/HTTP/JSON/业务失败及配置检查。
4. 最终轮次：补充实际 Postman 23 请求覆盖核对、HTTP 重定向防护、置顶排序负例；结果见下方最终状态。

验证命令（仓库根目录）：

```bash
.venv/bin/python -m pytest -c apps/velowind-app/api-tests/pytest.ini apps/velowind-app/api-tests/tests -q --junitxml=.tmp/private-chat-api/unit-results.xml
```

报告：`.tmp/private-chat-api/unit-results.xml`。历史失败结果以上述记录保留，不用后续通过覆盖。

## 最终状态

最终复核：39 passed、1 skipped，耗时 5.77 秒。新增验证还包括 CLI 成功/失败/配置阻断退出码、报告文件权限和掩码凭据拒绝。

对实际 G1 导出执行 `--check-config`：退出码 2，报告状态 `blocked`，原因为 `Missing/unresolved variable: base_url`。报告 `.tmp/private-chat-api/config-check.json`，请求列表为空。

真实后端：未验证；需包含真实本地值的环境文件（base_url、三组 phone/password、post_id、activity_id），随后执行配置检查与完整流程。不得将 skipped 或本地 HTTP 服务通过称为后端通过。

实际清理：本次未向真实后端发送请求，无本轮新增业务数据；脚本真实执行后不自动清理，报告会单独标识。

真机验证：未执行，独立 API 测试不竞争 Appium/pytest 真机会话，也不证明 UI 通过。


## Allure 接入（后续轮次）

用户要求改用 Allure。CLI 默认输出 `.tmp/private-chat-api/allure-results`，pytest 入口支持原生步骤和附件；保留辅助 JSON。配置检查与业务用例拥有不同身份；断言失败显示 failed，配置/HTTP/网络异常显示 broken。结果按 UUID 追加，不清除历史。

首轮接入验证：43 passed、1 failed、1 skipped。失败原因是原离线用例读取已被填写实际数据的业务示例，导致变量缺失测试不再缺值。将离线场景移入 `tests/fixtures/scenario.json`，不改用户的本地数据。

最终验证：44 passed、1 skipped。命令：`.venv/bin/python -m pytest -c apps/velowind-app/api-tests/pytest.ini apps/velowind-app/api-tests/tests -q --alluredir=.tmp/private-chat-api/allure-verification-results`。Allure HTML 输出 `.tmp/private-chat-api/allure-verification-report`。

本轮报告接入没有重跑真实写接口。前一轮实际运行已确认 A/B/C 登录、A关注B成功，B未读基线为26，与预期0不符后停止，没有发送本轮私信；真实整套仍未通过。之前的“真实后端未验证”是早期状态，以此轮补充为准。


## API 请求响应附件与快捷命令

每次 HTTP 调用记录脱敏 request/response，CLI Allure 与 pytest 原生 Allure 均嵌套在对应业务步骤。HTTP错误与非JSON正文保留；无响应明确说明原因。已测试成功响应、401 JSON/文本、网络失败、附件关联、凭据与回显脱敏，以及业务返回值不被脱敏修改。

首轮44项旧测试中有1项失败：Python 3.9 的 HTTPError 测试夹具没有实际流，读取错误正文触发 KeyError；改为真实 BytesIO 流后通过。

新增 package.json 快捷命令 api:private-chat、api:private-chat:check、api:private-chat:report、api:private-chat:unit。执行 `pnpm api:private-chat:unit`：49 passed、1 deselected（真实用例未运行）。本轮不新增真实私信，不改变此前基线26导致终止的结论。


## 2026-09-18 Allure失败修复与真实复测

修复可重复运行的历史未读准备（仅B→A会话）、21秒发送节奏，以及接收侧clientMessageId按后端设计为null的断言。离线60 passed，1 deselected。

真实第三轮：基线3→0→发送后3，8条文本、置顶、隐藏、笔记分享通过；活动分享HTTP400/17000025，整套仍未通过。独立只读复核B四条（3文本+笔记）、C五条文本均通过。另一公开活动分享也返回同样provider错误。已增强HTTP错误摘要业务码/messageKey。

三轮失败和后续局部成功分别保留；详见appium/docs/test-fixes的2026-09-18-api-private-chat三份记录。未删除历史，成功发送消息和会话状态未回滚；真机未执行。下一步需后端修复活动卡片provider，不能通过放宽断言宣称整套通过。


## 控制台进度与运行结束自动打开Allure

- 新增即时flush日志：业务步骤、API结果、发送进度、未读计数与等待间隔。不输出认证配置和正文。
- `pnpm api:private-chat` 默认传入 `--open-report`；成功/失败后均生成HTML并后台启动Allure浏览器，失败退出码保留。配置检查不打开。
- 验证69 passed、1 deselected；覆盖成功/失败打开、生成失败、缺少CLI、禁止覆盖原始结果及日志敏感信息不泄漏。
- 使用已有真实结果验证报告生成与启动，不重新发私信；原有活动provider阻断结论不变。
