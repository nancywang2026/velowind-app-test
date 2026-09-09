# 消息系统自动化

已实现 8 条流程、13 个参数化场景，使用现有 Appium + pytest 工程。所有 UI 查找集中使用 `AppiumBy.ACCESSIBILITY_ID`；长按和滚动使用已定位元素的 ID，不使用坐标、文字或 XPath 兜底。

当前为待接入的自动化实现：本仓库没有 App 前端源码，也没有已确认的消息测试数据接口。配置中的 `message.*` 是需前端实现或替换的标识契约，不能视为已经在 App 上验证过的 ID。演示数据原型不具备验证真实收发、权限和持久化的条件。

## 文件与范围

- `config/test_data.yaml`：账号环境变量名、数据准备、输入、预期、超时、参数化场景。动态实体 ID 来自每次准备结果；脚本不保存账号密码。
- `config/accessibility_ids.yaml`：全部控件标识及动态 `{id}` / `{category}` / `{decision}` 模板。
- `velowind_appium/message_system/`（从 Appium 工程根目录起）：配置加载、UI 操作、业务适配客户端和流程实现。
- `test_ios_message_system.py`、`conftest.py`：pytest 入口、账号切换和准备/清理。

| 流程 | 场景数 | 已实现检查 |
| --- | ---: | --- |
| A01 | 1 | 进入系统通知列表不清已读；逐条点击；重复点击；其他通知和互动计数保持 |
| A02 | 1 | 隐藏会话；新消息确认同步后首页仍不出现；隐藏列表仍存在；新旧消息保存 |
| A03 | 2 | 单聊/群聊发送及回复；发送人、会话、正文、重复数；不串入其他会话；群预览 |
| A04 | 1 | 空表单/未勾选协议不能提交；创建私密群；名称/简介/成员/群主正确 |
| A05 | 2 | 同意/拒绝申请；申请状态、成员集合、申请人发送权限 |
| A06 | 4 | 普通成员无管理入口；修改简介、可见性、审批、解散被拒且状态不变；群主修改简介成功作为正向对照 |
| A07 | 1 | 置顶至群列表首位；返回后保存；取消后保存；私聊集合不变 |
| A08 | 1 | 四类互动列表的完整事件集合；切换分类不标记已读 |

尚未自动化：A01 互动跨分类逐条已读变体、离线重连、长度边界组件测试、双真机接收 UI、推送、未知排序与新成员历史规则。YAML 中的 `deferred_coverage` 仅记录这些后续范围，不参与执行。不会猜测产品未确认的规则。

## 前端 accessibility 契约

修改 YAML 即可替换实际 ID；请保持语义键不变。Appium 使用 iOS `accessibilityIdentifier`，不能仅设置可见标题或 accessibilityLabel。

- `*.ready`：对应页面/列表已完成数据加载后可见，不能只是页面框架出现。
- `account.identity`、`chat.identity`：`value` 分别为实际用户 ID、会话 ID。
- `notification.read`：预留单条通知已读状态标识，本期 A01 以业务状态及首页计数交叉检查。
- 动态会话/消息/通知/申请控件使用业务实体 ID。`conversation.preview` 的值为正文预览，`chat.message` 的值为消息正文（不拼入昵称和时间）。
- `create.visibility`、`create.agreement`、`group.pin`：`value` 为 `0/1` 或 `false/true`；提交按钮正确暴露 enabled 状态。
- `group.first`：`value` 为群聊分区第一项的会话 ID，不涉及私聊排序。
- 集合 `home_conversations`、`hidden_conversations`、`private_conversations`、`interactions`、`owner_controls` 都包含 ready/total/item/end/container 标识。total 为完整结果总数；每行独立子元素共用 item 标识、value 为实体 ID；end 仅在完整列表末尾可见；container 为可滚动容器。业务行可另用动态 row 标识。
- `owner_controls` 在成员页仍提供空集合容器及 total=0/end，防止仅凭首屏没看见就判断管理入口不存在。
- 进入页面/重新点击消息 Tab 时列表回到顶部；切换分类后 ready/total/end 对应新分类。准备的目标会话、申请须首屏可操作，集合检查会向下遍历；超限或数量不符报失败。
- 群申请审批按钮在本期契约中点击即提交；如果实际有确认弹窗，需要补充独立 ID 和页面操作。登录契约为账号页进入账号密码登录。以真实 App 导航为准调整页面层。

## 测试数据适配服务契约

`MESSAGE_TEST_BRIDGE_URL` 是待实现/接入的测试专用适配服务，不是假定已有的产品接口。`bridge.py` 已实现 HTTP 客户端。服务应调用实际业务接口；不能直接把期望结果返回给测试，也不能用管理员身份代替待测成员身份完成权限验证。

统一 POST JSON：

```json
{"protocol_version":1,"run_id":"unique","case_id":"MSG-A03","variant":"group","operation":"read","payload":{"kind":"messages","entity_id":"conversation-id","text":"unique text"}}
```

请求鉴权为 `Authorization: Bearer <MESSAGE_TEST_BRIDGE_TOKEN>`。成功响应为 `{"ok":true,"data":{...}}`。传输失败、非法 JSON、非成功响应均失败；写操作不会自动重试。服务端应按 run_id/case_id/variant 隔离并登记资源，支持同一逻辑操作幂等处理。

| operation / kind | 输入和响应 data |
| --- | --- |
| prepare | 输入 setup（YAML）、accounts（角色到用户名）；根据 case_id/variant 准备真实隔离数据，返回 `runtime: {actor:{id},peer:{id},owner:{id},N1:{id},...}`；仅返回当前场景需要的别名及三类账号。A03 variant 决定单聊/群聊。A04 只准备创建资格，不创建群。 |
| send | 输入 sender_id/conversation_id/text，以指定发送者发送真实消息，返回 `{id}`。 |
| read: notification | 输入 entity_id；返回 `{id,read}`，read 为布尔。 |
| read: unread | entity_id 为用户 ID；返回 `{system,interaction}` 两个整数。 |
| read: conversation | 返回 `{id,hidden,pinned,message_ids}`；布尔状态必须来自持久化业务数据。 |
| read: delivery | entity_id 为消息 ID；返回 `{synchronized_user_ids:[]}`，必须确认客户端同步/实际接收，不能将服务端接受发送等同接收。无法观察时应报不支持并阻塞该流程。 |
| read: messages | entity_id 为会话 ID，text 为精确正文过滤；返回 `{items:[{id,conversation_id,sender_id,text}]}` 完整集合，不截断分页。 |
| read: group | 返回 `{id,name,description,public,owner_id,member_ids}`。 |
| read: created_groups | 输入 name；仅查询当前运行通过 UI 新建的群，返回 `{items:[完整 group 对象]}`，并登记这些群以便失败时清理。即使 UI 创建后脚本尚未查询，cleanup 也必须能找到群。 |
| read: application | 返回 `{id,status}`，status 归一化为 pending/approved/rejected。 |
| read: permission_snapshot | entity_id 为群 ID，application_id 为申请 ID；返回精确的 `{description,public,members,application_status,group_exists}`，members 按 ID 排序，排除更新时间等易变字段。 |
| permission_probe | actor_id/group_id/application_id/operation_name/input；以 actor 的真实认证调用对应业务操作，返回 `{allowed:布尔}`。operation_name 为 send_message/edit_description/edit_visibility/approve_application/dissolve_group；从 input 取 permission_probe_text/description/public。鉴权失效、网络错误、参数错误不能算权限拒绝，应报错；成功发消息须登记待清理；返回前确认业务操作已完成，避免异步写入绕过紧接着的状态快照断言。 |
| cleanup | 无额外输入；按运行标识清理本次通知、消息、申请、新建群并恢复账号状态，返回 `{remaining_ids:[]}`。未准备成功也必须可调用；清理失败作为 pytest teardown 错误保留。 |

使用三个互不相同的测试账号，测试服务管理对应测试身份凭据。prepare 要隔离或还原账号既有通知、会话等状态，使 YAML 的确切计数成立。所有种子和 UI 创建资源属于本次运行；不得全库清理。A06 准备的简介需与待修改文本不同。A07 准备目标不在首位且无其他置顶群；私聊分区需有可检测污染的基线数据。原型静态画面不能代替此适配服务。

## 执行

在 Appium 工程目录运行，沿用现有 `ios-appium.yaml` 的设备和服务配置。仅串行运行，禁止 xdist。

```bash
# 本地验证，不连接设备
../../../.venv/bin/python -m pytest tests/unit-test/test_message_system.py -q
# 接入完成后执行真机流程；账号密码通过环境或密钥管理器注入
export VW_MESSAGE_AUTOMATION=1
../../../.venv/bin/python -m pytest tests/message_system -v
# 仅隐藏会话场景
../../../.venv/bin/python -m pytest tests/message_system -k MSG-A02 -v
```

运行前需要 `MESSAGE_TEST_BRIDGE_URL`、`MESSAGE_TEST_BRIDGE_TOKEN`，以及 YAML 中各账号 username_env；当前场景的 actor 还需要 password_env。可通过 `VW_MESSAGE_DATA_FILE`、`VW_MESSAGE_LOCATORS_FILE` 指向环境专用配置文件。

默认未启用时 13 个真机场景显式 SKIPPED/BLOCKED，不能当作业务通过；启用后缺配置直接报错。每例独立准备、登录、执行并清理，失败继承现有截图/XML/Allure 附件机制。登录发生在 fixture 阶段，其失败可能没有父级 call 阶段截图，应检查 Appium 日志。当前只验证本地逻辑，不声称已完成真机回归。

本地验证记录：24 项脚本逻辑测试通过；13 个真机场景因尚未接入而跳过。未执行真实收发和群管理回归。
