# 2026-10-19 消息功能脚本接入

## 范围与当前状态

- 用户要求：实现 CSV 确认后的全部消息功能点，通知追加到原发布/报名/评论/关注操作后，私信包含阅读图标及最新消息定位。
- 用户明确账号来源：Postman A/B/C。
- 已新增 `message_regression` 执行基础、34 组59分支流程定义及独立 pytest 入口；**具体真实操作绑定尚未实现，不能声明全部消息自动化完成**。
- 54 项离线测试通过；真机消息回归、支付、数据清理均未执行。
- 历史参考：[模拟支付回调](2026-10-19-payment-mock-callback.md)、[测试环境映射](2026-10-19-test-api-environment.md)、[系统通知入口](2026-10-19-system-notification-entry.md)。仅复用已确认契约，不把历史通过当本轮结果。

## 分析证据

- 原 `tests/message_system` 依赖尚未部署的桥接服务，包含本轮排除的隐藏/恢复、审批和公开设置；未直接扩大该 suite，也未破坏旧13个场景。
- 读取本地 Postman 私聊、群聊、互动、评论@、隐私、活动群等 collection；确认若干实际接口。未执行原 collection 的整套写入或猜测缺失接口。
- 读取历史 XML：仅少数稳定标识，如 `bottom-nav-message`、`chat-conversation-subpage-header`；逐条已读图标等缺少可核验标识，未填虚构ID。
- 早先发现 PID 32435 等真机 suite；本轮后续进程检查无 pytest，4785 `/sessions` 返回 URLError，未重启服务器或新建手机会话。
- Postman 经正常UI导出 `0 - dev` 和私聊A/B/C环境，两份导出均缺有效账号及base_url。临时文件0600；已向用户请求有效配置路径，不输出凭据。
- dev-api OpenAPI 只读尝试未取得响应，未以此推断生产故障；仍采用现有导出契约并保留未核实项。

## 第1轮：实现及离线验证

### 修改

- `core.py`：受限环境、认证业务HTTP、分页边界、防重游标、清理结果登记；不自动重试写请求，不记录密码/token/完整认证响应。
- `business.py`：通知基线与目标匹配、私信接口/历史、关注恢复、建群/成员、真实@与回复API方法。
- `native.py`：有证据的原生定位、唯一性检查及可见性几何断言。
- `program.py`、`journeys.py`：全流程预检与34组59变体断言；缺绑定阻塞，准备/断言失败都执行本轮清理，保留原始失败并另报cleanup-pending。
- `hooks.py`：提供原业务操作后追加通知的调用钩子，未插入原发布/报名脚本。
- 独立 `tests/message_regression`：默认不连接设备；启用也先核对配置、能力、占用及身份；无伪造准备响应。

### 验证命令与实际结果

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_message_regression.py \
apps/velowind-app/appium/tests/unit-test/test_payment_mock.py -q -o addopts=''

PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression \
--output outputs/message-automation-20261019/coverage-audit.json

VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/message_regression --collect-only -q -o addopts=''
```

- 54 passed，0.12秒；既有LibreSSL warning。报告目录 `.tmp/appium-ios/runs/20261019-223019-66000/timing/`。
- 59 tests collected，0.01秒；不是59条通过。报告目录 `.tmp/appium-ios/runs/20261019-223413-67642/timing/`。
- 绑定审计：34组均blocked；缺准备/业务/UI观察/清理操作绑定。审计文件 `outputs/message-automation-20261019/coverage-audit.json`。
- 代码静态编译通过；后续配置验证修补仍需重跑受影响离线测试。

## 无效尝试及边界

| 尝试 | 实际结果与原因 |
| --- | --- |
| 用旧message_system直接覆盖全部功能 | 不适用，含10月排除项且桥接服务未接入 |
| 从已有导出环境获取账号 | 原导出为空；本轮从Postman重新导出仍为空，不能假造凭据 |
| 用旧XML直接推断已读图标定位 | 证据不足，历史只见“已发送”等标签，不等于未读/已读 |
| 用同步接口声称遍历全部旧私信 | 不适用，afterMessageId是向前同步；另保留UI历史断言 |

## 第2轮：原发布流程扩展与验证

- `tests/shared_publish_note.py` 增加可选 `notification_observer`：发布前抓消息基线，提交后由observer确认实际发布终态并验消息，最后才清理；observer失败也执行原笔记清理。默认不传observer时保持原流程。
- `tests/activity/test_publish_activity.py` 提取可复用 `run_publish_activity_case` 并增加同样的可选接口；默认测试仍沿用原发布步骤，未伪造活动清理能力。
- `publication.py` 提供observer适配器，当前实体ID解析及真实终态查询需实际业务配置，不能将“待审核”直接判消息成功。
- 新增离线测试确认只有一次发布、消息检查在清理前、通知失败清理仍执行；扩展原生唯一性/可见几何、配置空值、真实API返回断言测试。
- 运行 `test_shared_publish_note.py`、`test_publication_notification_hooks.py`、`test_message_regression.py`、`test_payment_mock.py`、`test_message_system.py`：89 passed，0.43秒；既有LibreSSL warning。
- 报告目录 `.tmp/appium-ios/runs/20261019-224110-70440/timing/`；89包含既有测试，不是89条消息业务真机通过。
- 默认未启用运行新suite：59 skipped，0.08秒，不连接设备；目录 `.tmp/appium-ios/runs/20261019-223849-69560/timing/`。
- `git diff --check`、静态编译通过。真实observer、其余业务绑定和真机仍未验证。

## 遗留项与交接

### 2026-10-20 账号文件格式调整

- 按用户要求将用户名、密码、ID归入同一账号对象；私有文件改为 `.private/message-regression/accounts.json`，分为 `accounts.a/b/c`，保留全部原值，不在记录中输出凭据。
- `execution.json` 更新为 `accounts_file` 引用；加载器新增分组格式、配置相对路径及环境变量覆盖，继续兼容原Postman格式。文件0600、目录0700，Git忽略检查通过。
- `test_message_regression.py`：34 passed，0.08秒，包含分组读取、环境变量覆盖不写回、异常结构不泄露内容等验证。目录 `.tmp/appium-ios/runs/20261020-094949-72411/timing/`。
- 没有登录、真机或线上写入；其他消息接入遗留项保持不变。

- 必须补齐真实操作绑定、有效ABC配置、发布observer实际解析/查询、报名等原业务脚本钩子接入、身份切换/设备归属、媒体上传和读图标观察、活动报名支付/退款reader。
- 隐私矩阵、历史可见规则、故障注入仍是明确的能力条件；无条件不得通过。
- 下一步先拿有效账号及设备只读现场证据，接入一条完整文字私信含收件UI/图标/清理链路，再按审计逐组接入其他场景；不是让用户手工填写所有操作绑定。
- 真机：未验证。线上业务数据：本轮未创建/修改。清理：不涉及，不能归为34组实际清理通过。

## 第3轮：2026-10-20 真实接口接入与独占真机

### 前提与已确认事实

- 用户确认 A/B/C 已配置，随后明确 Zhigang 的 iPhone 可独占。检查无其他 pytest 运行，使用独立4790端口；未结束其他 Appium 服务器。
- A/B/C 实际登录及个人资料身份核对通过；报告只保留成功状态，不记录密码/token/完整认证响应。
- 通过无代理只读取得当前 dev-api OpenAPI（847路径），纠正之前尚未执行的群详情包装、成员ID与搜索路由、beforeMessageId历史分页和通知querySnapshot契约。
- Appium3 `/sessions` 返回404，不能据此断言没有会话。早先自有会话因闲置失效；在用户确认独占后重建自有会话并延长newCommandTimeout。旧通用绑定suite的会话发现限制尚待适配。
- 真机1.3.0 build64，当前C身份。实际观察到本轮在dev-api创建的唯一群名及C发出的唯一私信，证明当前数据互通；尚未抓取App网络host，支付环境门禁不因此放宽。

### 新增真实执行入口

- `message_regression/live.py`：直接从本地分组账号文件登录，无需手填operations绑定。群聊在同一个新建群上顺序执行；写请求不自动重试，创建结果未知按本轮唯一群名核查；finally解散并查询只读终态。
- 真实群聊首轮8组接口断言全部通过：创建/成员、邀请同意拒绝、重新邀请/搜索、各用户置顶免打扰独立持久化、改名公告版本、5条消息旧历史分页及顺序、个人清空不影响他人、移除与退出。
- 报告 `outputs/message-automation-20261020/live-first/live-results.json`；本轮测试群确认 `DISSOLVED_READ_ONLY`，产品仍保留只读历史，不宣称物理删除。
- 第二个测试群实际在C真机列表及详情显示，本轮8组API加1组UI观察通过，随后确认解散；`outputs/message-automation-20261020/native-group/`。解散后真机出现“该群已解散”，输入框外观仍存在，发送禁用尚未测试。
- 私信C→A三条，收件未读基线0，实际0→3→0；发送内容、INBOUND接收方向及历史ID匹配通过。保留消息ID，不清空既有会话；新增私信属于明确残留，不能算已删除。
- 初次私信UI采集仅观察，不包含完整已读断言，`native-private`中原native两行应视为观察记录。实际两次XML均“已发送”；不得用这些采集步骤当已读图标通过。
- `ios_live.py`新增基于当前XML的唯一目标、消息对应状态、重新进入、最新消息与输入框几何断言；正在按真实断言复跑。未覆盖图片、浏览旧历史不抢滚动、完整通知业务链和支付退款。

### 离线验证

- 修正契约后相关消息/通知hook/支付离线62 passed；目录 `.tmp/appium-ios/runs/20261020-101104-81810/timing/`。
- 新增before分页、通知快照、防敏感信息HTTP错误、成员搜索及群详情回归，消息39 passed；目录 `.tmp/appium-ios/runs/20261020-101228-82026/timing/`。
- 整套34组59分支仍未全部真实绑定/验证；上述API与UI结果严格分别记录。

## 第4轮：真实断言、媒体、互动和管理端

### 已确认的执行结果

- 用户补充 A 有管理员权限；使用 A 原账号完成 `/admin/auth/login` 与 `/admin/auth/session` 身份核对。只读验证管理端会话，没有修改密码、角色或环境开关。
- 最终群聊 `outputs/message-automation-20261020/group-final/live-results.json`：13项中12 passed、1 blocked。增加了A/B/C双向消息、普通成员改名/解散拒绝及状态不变断言。成员编辑公告实际返回400/17000106 `message.mobile-center.capability-unavailable`，不能将其当已证明“owner_required”；其他独立断言继续执行。
- 群图片用本轮生成的64×64 PNG，经真实OSS策略上传及真实ETag回调，由两个不同成员分别发送。接收端与重新查询的accessUrl完整字节SHA256均匹配。测试群均确认解散，只读历史及已上传资产保留，资源ID在报告中。
- 私信 `native-private-asserted`：3项API passed；发送侧未读/发送态、重进后最新消息在输入框上方的UI断言 passed；收件API读3条后，发件UI等待并重进仍显示“已发送”，已读图标断言 failed。不是私信全部通过。两轮累计新增6条私信保留，不清空既有会话。
- 互动 `comment-notifications-unfiltered`：复用C已有可评论笔记，准备、A真实结构化@C及通知、B回复A及通知、B点赞A评论及通知4项 passed；B收藏已生效且计数1，但30秒未找到收藏通知，failed。对应评论与回复已删除，点赞/收藏计数实际回到0。
- 取消互动当前响应 `active=true`，与文档false不同；最终清理改为查询本轮新评论的实际计数归零后才删除。早一轮 `comment-notifications-final` 的2个取消响应断言失败保留，不能改写为该轮所有清理通过。

### 无效尝试与修正

| 尝试 | 实际证据、修正与限制 |
| --- | --- |
| 图片发送200后立即按文本回执断言 | 第一轮 `group-images` 内容断言失败；此时图片仍异步处理中，finally解散后结果为FAILED。新增结果查询等待SENT/FAILED/UNKNOWN，不重发；`group-images-confirmed` 9 passed。不能推断原图片一定被审核拒绝 |
| 评论列表直接断言likedByCurrentUser | 实际字段缺失，立即断言及30秒轮询两轮均失败；新建独立评论的初始计数0，实际认证写入active和计数0→1足以核对本轮互动，按此查询后再验证通知。字段差异保留，不假造该字段为true |
| 直接筛选尚未核实的CONTENT_COMMENT_FAVORITED | 服务端筛选请求500；改为遍历INTERACTION完整列表后在客户端精确筛选。最终无收藏通知，仍按failed，不因回避500改为通过。已存在的本轮通知只含回复及点赞 |
| 原笔记observer按原始draft.title查新笔记 | 原公共发布逻辑会生成8位前缀并截断标题；首轮UI发布passed（140.268秒）、通知解析60秒超时、原清理passed。新增读取driver._api_note_publication的真实标题/ID和前后ID基线，禁止审核旧同名笔记 |
| 修正标题后复验原笔记发布 | `note-publication-notification-scoped` 在原发布步骤205.894秒失败，现场“我的笔记”显示加载失败；没有进入通知断言。原始截图/XML位于 `.tmp/message-live-20261020/note-failed.*`，不能声明笔记通知通过 |
| API预检偶发登录502 | 后续只读管理/关注契约查询遇到502，未自动重试登录，未据此认定密码错误；暂不把当前发布失败归因于登录/服务/令牌，原因未确认 |

### 新代码与可执行方式

- `ios_live.py`：仅附着显式自有会话，检查C身份；基于实际XML关联每一条消息状态，验证重进及最新消息几何；不创建或替换手机会话。
- `media.py`：本轮确定性图片、受限HTTPS媒体host、签名策略multipart上传、真实ETag、完整字节校验；不记录临时密钥、策略或签名URL。
- `interactions.py`：接受原业务测试的C作者post_id，不另建笔记；@/回复/赞/收藏后通知和本轮清理。未知评论创建结果按本轮唯一正文及作者核查，未核实则cleanup-pending。
- `PostPublicationObserver`、`publication_live.py`：直接复用原笔记发布函数；仅选择基线之外的新ID、实际随机标题及创建时间符合的笔记，核对作者侧内容，必要时用A审核当前revision，再查真实终态和通知；默认不更改审核策略。当前原生通知列表定位仍待此发布链成功后验证，目标跳转/返回未验证。
- `payment_mock.py`增加 `read_activity_enrollment`：真实报名详情和收银台交叉核对付款人operatorUserId、enrollmentId、paymentOrderId、金额、MAIN/FULL_AMOUNT与ALIPAY。7项新增离线测试；实际付费报名、支付回调及退款未执行。
- `test_live_messages.py` 提供20个具体pytest入口，模块fixture复用同一个群/同一笔记，实际case与cleanup分别报告。需显式启用；不依赖早期operations JSON。20 collected不等于20 passed。

### 本轮验证与未完成事项

- 相关消息、支付、通知钩子及既有公共发布/旧消息离线共110 passed，目录 `.tmp/appium-ios/runs/20261020-103957-88081/timing/`。新增scope/清理补丁仍需最终重跑相关测试。
- 全部34组59分支仍未完成。剩余包括活动原发布/报名取消退款实际链、管理端拒绝流、私信图片/清空/分享、浏览旧历史不抢滚动、完整目标跳转返回、条件故障注入和10月候选隐私范围。
- 已读图标、收藏通知及发布页加载失败需要保留真实失败；不得改断言为通过。管理端A权限已确认，不再让用户另配管理员账号。
- 不涉及生产环境写入、角色修改、审核开关变更或真实渠道支付。

## 第5轮：历史消息定位与原报名用例接入

- `ios_live.py --suite history` 首轮 `private-history` 4项通过；旧历史锚点390→390，在底部收到新消息后可见且未被输入框遮挡。但首轮只等2秒，没有充分证明检查锚点前客户端已处理消息，不能单凭首轮宣称“不抢滚动”完整通过。
- 强化收件前提后的 `private-history-confirmed`：基线与准备passed，客户端处理后同一锚点183→133，偏移50像素，断言failed；后续底部用例未执行。保留失败，不能被首轮结果覆盖。尚未确认是滚动惯性、动态布局还是来信引起。
- 新增三次稳定采样后才记录基线；重跑 `private-history-stable` 中。没有放宽3像素断言容差。所有本轮来信ID登记为保留，基线为0时实际清理本轮未读计数，不清空既有会话。
- `EnrollmentObserver` 新增本轮ID基线、创建时间和operatorUserId校验，原报名用例提取为 `run_activity_signup_case`：提交前通知基线，原订单提交一次，之后实际CONFIRMED通知/群入口、本报名单取消或A管理端拒绝、实际退款SUCCEEDED通知；finally清理范围仅本轮报名单。默认未传observer仍保持原测试流程。
- 报名拒绝请求使用当前OpenAPI `rejectReason`；只读核对A已有报名状态包含CANCELED/CONFIRMED/REJECTED及实际退款SUCCEEDED，没有修改这些已有订单。付款reader兼容领域WAITING_PAYMENT与客户端PENDING_PAYMENT。
- 报名observer目前未接入完整可执行付费场景：实际确认支付动作/环境证据及支付callback completion仍需传入并实测，未运行任何实际活动支付、拒绝、取消或退款。活动群入口只核对本session的READY/ACTIVE/sendAllowed，不选另一个活动顶替。
- 新增4项离线测试验证：原报名只提交一次、通知失败仍清理、提交超时不重试且仍清理、不取消基线旧单、退款失败不算清理成功（含组合断言）。相关suite合计114 passed，0.51秒；目录 `.tmp/appium-ios/runs/20261020-105438-90400/timing/`。
- 新具体pytest入口默认运行20 skipped，未登录/未连接设备/未写数据；`.tmp/appium-ios/runs/20261020-104752-88957/timing/`。与实际API和真机结果分开统计。

### 第5轮后续结果与当前交接

- 三次稳定采样后的 `private-history-stable`：准备passed（19.747秒），确认客户端处理来信后锚点208→182，仍偏移26像素，旧历史位置断言failed（5.528秒）。底部测试本轮因前置失败未执行；首轮底部最新定位通过的证据保留，不能替代旧历史位置失败。未将偏移原因归为已确认的服务端或客户端根因。
- 所有本轮已观察到的两组随机笔记标题，通过C作者侧ALL列表再核对，当前匹配0、剩余0，没有扩大删除范围；结果 `outputs/message-automation-20261020/publication-reconciliation.json`。原发布流程第一次清理passed、第二次没有查到当前新笔记，仍分别记录原断言失败。
- 最终相关离线110 passed，0.48秒复跑（含旧逻辑），目录 `.tmp/appium-ios/runs/20261020-104442-88669/timing/`；加入报名4项后114 passed见105438目录。历史定位稳定采样与准备条件属于后续修改，不以这些单元通过替代真机失败。
- `git diff --check` 与新增模块静态编译通过。统一状态 `outputs/message-automation-20261020/implementation-status.json`；全量34组59分支未完成。
- 当前明确失败：私信已读图标、评论收藏通知、旧历史来信后位置漂移、原笔记发布链“我的笔记”加载失败。活动报名observer、管理审核及支付reader仅已接代码/离线验证，实际支付取消退款未验证。
- 下一步：先处理上述真实失败的证据与接口/界面差异，再补齐实际活动发布/报名及支付退款运行器、私信图片清空分享、完整通知目标跳转返回；候选隐私和故障注入仍需实际能力。A管理员身份已确认，不重复索要账号。

- 最终复跑相关6份测试文件：114 passed，0.50秒，`.tmp/appium-ios/runs/20261020-110102-91491/timing/`。最终检查没有运行中的pytest、publication_live或ios_live脚本。
- 资源汇总按实际ID去重：6个本轮群（均解散为只读）、5个保留图片资产、10条保留私信、8条已删除评论；不是生产资源。API通知记录仍按产品保留，没有批量已读或删除原有消息。
- Zhigang iPhone 已返回消息列表；本任务4790 Appium 自有会话保持空闲，可在用户已授权的独占范围内继续复用，未结束其他 Appium 服务器。会话标识保存在 `.tmp/message-live-20261020/owned-session.json`；下一轮先检查占用与会话有效性，不直接替换。

## 第6轮：用户要求运行私信相关用例

### 执行前检查与范围

- 复读本索引及本记录；检查未发现其他pytest/publication_live/ios_live进程。4790仍为本任务自有Appium，既有会话有效，复用而未创建/替换会话。用户此前对Zhigang iPhone的独占授权继续适用。
- 执行当前已接入的私信真实API及C发件UI检查，并独立执行底部连续来信检查。没有运行群聊、管理审核或支付。

### 命令与实际结果

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.ios_live \
  --accounts .private/message-regression/accounts.json --session .tmp/message-live-20261020/owned-session.json \
  --output outputs/message-private-20261020-rerun/receipts --suite private

PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.ios_live \
  --accounts .private/message-regression/accounts.json --session .tmp/message-live-20261020/owned-session.json \
  --output outputs/message-private-20261020-rerun/history --suite history

PYTHONPATH=apps/velowind-app/appium .venv/bin/python .tmp/message-private-20261020-rerun/run_bottom.py
```

- 收发/阅读组：4 passed、1 failed，退出码1。三条文字发送、接收内容/方向、顺序、未读0→3→0、进入与重进最新定位通过。收件A已读后，C侧等待并重进，本轮三条依旧“已发送”，逐条已读显示失败。证据 `receipts/read-reentered.xml`；summary逐条关联本轮消息ID与实际显示。
- 旧历史组：2 passed、1 failed，退出码1。基线与稳定锚点准备通过，确认客户端处理新消息后锚点168→141，偏移27像素，位置保持失败。证据 `history/older-history-stable-before-incoming.xml`、`older-history-after-incoming.xml`。本组后续底部检查因原流程前置失败未执行。
- 独立底部组：5 passed，退出码0。复用相同API、OwnedIOS定位和几何断言，重新进入底部后A向C连续发送三条唯一消息，逐条在不重新进入会话的条件下等待其可见且不被输入框遮挡；收件内容/方向和未读自动归零通过。独立执行不覆盖或撤销旧历史失败。
- 合计13项子检查，11 passed、2 failed；包含数据前置/计数子检查，不等于13个独立业务场景，也不是私信全功能通过。

### 数据与交接

- 本轮新增7条私信保留，ID在 `outputs/message-private-20261020-rerun/summary.json`；没有清空原会话历史。A侧本轮三条已读，C侧本轮来信未读已实际归零，没有unread_cleanup_error。
- 本轮未修改测试断言或业务代码，只新增独立底部执行脚本与报告/记录。图片、私信清空、卡片分享和故障恢复未执行，完整原生用例仍待接入。
- 人读报告 `outputs/message-private-20261020-rerun/README.md`；原始分组结果在同目录receipts/history/bottom下的live-results.json。密码、token、完整认证响应均未写入报告。
- 当前应保留并继续定位的失败：逐条已读显示；旧历史来信后位置漂移。底部连续跟随与会话重进最新定位本轮通过，不能替代上述失败。

## 第7轮：独立运行器缺少 Allure 报告

### 证据与原因

- 用户指出第6轮缺少Allure。已确认直接运行Python模块绕过pytest及其Allure采集；原来仅写live-results.json和XML。不是业务检查没有执行。
- 无效尝试：`allure generate --help` 被当前CLI当成输入目录，生成根目录空报告（total=0）；没有作为测试结果使用，核实为空后已删除。

### 修改及验证

- 新增 `message_regression/allure_report.py`，从实际完成记录导出Allure标准JSON；running不计入，blocked映射skipped，未知状态报错，失败保持失败。仅复制允许字段和实际存在的分组XML，不复制账号配置或认证响应。
- `LiveRun.save()` 自动写每轮allure-results；新case保存真实毫秒起止时间。历史记录没有起止时间，保持缺失，原单调时钟耗时作为参数显示；没有伪造执行时间或逐步骤截图。
- 第6轮receipts/history/bottom原记录合并补生成 `outputs/message-private-20261020-rerun/allure-report`。安装的Allure CLI生成成功，widgets/summary.json及本地HTTP读取均为total13、passed11、failed2，其余0。XML保留，当前两项失败没有改写。

```bash
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_message_allure_report.py apps/velowind-app/appium/tests/unit-test/test_message_regression.py -q
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.allure_report --input outputs/message-private-20261020-rerun --results outputs/message-private-20261020-rerun/allure-results --report outputs/message-private-20261020-rerun/allure-report
```

- 离线第一轮48 passed；补充LiveRun成功/失败自动导出集成断言后49 passed，0.15秒；计时目录 `.tmp/appium-ios/runs/20261020-111818-93808/timing/`。检查状态映射、缺失时间、真实时间、附件存在、重复导出幂等及未导出任意账号字段。
- 当前HTML本地服务 `http://127.0.0.1:18864`，已请求在Codex打开。服务结束可按结果README命令重新打开。
- 本轮没有重新执行真机、登录API或发送消息；清理状态沿用第6轮的实际记录，没有新增资源清理。未来真机入口自动导出的设备实跑未验证，离线集成已验证；本轮HTML来自既有真实运行证据。
- 已完成报告补齐及后续原始结果自动采集；HTML生成仍使用显式生成命令，避免每次增量save启动CLI。全消息覆盖及原有两项业务失败仍未解决。

## 第8轮：用例测试内容、验证点与截图

### 原因、修改与离线验证

- 用户要求每项有测试内容、验证点和截图。原Allure只有技术用例名、导入说明和分组XML，缺少中文业务描述及PNG；第6轮没有采集PNG，不能补造旧现场。
- 新增 `case_descriptions.py`：覆盖当前13项私信检查及同源底部单项的中文标题、测试内容、准备、执行、验证点。描述区分接口已读返回与发件端逐条回执，不将尚未实现的断言写成通过结论。
- `OwnedIOS.snapshot` 同时采集真实Appium PNG；`bind_evidence` 让每个case结束（含失败）采集专属PNG，API用例画面明确标为辅助，不替代接口证据。截图失败只记录异常类别，不覆盖原断言错误。
- Allure只使用该case显式关联PNG，校验本组目录和PNG签名，避免把其他用例截图配给当前用例。旧结果无截图时明确注明缺失；无补造步骤或时间。
- 独立底部脚本相同断言移入 `OwnedIOS.bottom_incoming`，新增 `--suite bottom` 可重复入口，不再依赖临时脚本。
- 离线52 passed，0.14秒；目录 `.tmp/appium-ios/runs/20261020-112830-95020/timing/`。含全部私信描述/PNG关联、截图失败保持原失败、Appium截图返回保存断言。真实截图重跑正在执行，结果待追加，不以离线通过替代真机。
- 执行前未发现pytest/ios_live/publication_live或底部脚本占用；4790仍本任务自有服务器，复用原会话，不替换或终止其他服务。新报告独立目录 `outputs/message-private-20261020-screenshots/`，保留原13项11通过2失败结果。

### 第8轮真机初次失败及继续执行

- 收发组前2项passed；进入会话的最新定位检查超时failed，结束PNG显示桌面。现场 `mobile: queryAppState` 返回2（后台），当前只能确认应用不在前台，不能把原因确定为崩溃或截图导致。
- 失败记录及 `receipts/case-private.native-sent-state-and-latest.png` 原样保留，未将恢复后的画面替换该失败现场。此时已发送的3条私信没有重新发送。
- 重启应用后，以同一run_id、原消息ID和原结果继续剩余2项（临时脚本 `.tmp/message-private-20261020-screenshots/continue_receipts.py`）。先核对当前A未读恰为3，再执行原3条已读断言，passed；逐条已读显示仍failed，有3张真实关联截图。初次失败不撤销。继续脚本吞异常并保留case状态，其退出0不代表业务全通过，以case结果为准。
- 当前收发组完整5项：3 passed、2 failed，每项有结束PNG；其中进入会话超时为本轮新增失败，逐条已读失败为既有问题。继续执行没有创建新测试消息；本轮3条已读接口实际返回已标记3、未读0。
- 本轮追加关键阶段PNG也绑定到当时运行case；路径越界拒绝、仅关联运行case测试加入后，离线54 passed，0.16秒；目录 `.tmp/appium-ios/runs/20261020-113106-95556/timing/`。

### 第8轮范围追加：文字图片顺序和显示优先

- 用户明确重点为私信文字/图片正常发送、顺序及显示正确。新增 `private_mixed.py` 与 `--suite mixed`，明确区分真实API发送和真机接收显示，未宣称覆盖输入框和相册按钮。
- 依据当前dev OpenAPI `/api/v1/mobile/oss/client-upload-config` 描述支持 `PRIVATE_MESSAGE_IMAGE`。复用现有群图片直传与回调实现，提取公共 `upload_message_image`，私信使用peer targetId；两张图片用不同seed，防止同图通过掩盖顺序错误。
- 发送TEXT/IMAGE/TEXT/IMAGE/TEXT；图片复用现有SENT轮询和未知结果禁止重发；双方历史按实际返回顺序过滤本轮ID核对，不先排序再声称顺序正确。两侧图片核对assetId、AVAILABLE及完整字节哈希。
- 原生显示使用唯一文字锚点和中间图片区域，排除小头像；真实PNG采样33/36以上匹配输入图片，避免空白、占位及错图假通过；重进重复核对。该定位需当前真机实测，离线测试不能替代。
- 相关离线57 passed，0.15秒，目录 `.tmp/appium-ios/runs/20261020-113622-96263/timing/`。含反序历史、错误方向、缺图、头像排除、白图与错图拒绝。mixed真机执行中，结果待追加。
- 历史组本轮2 passed/1 failed、底部连续组5 passed，均已按case采集PNG；原13项当前合计10 passed/3 failed，包含前台丢失的新失败。不能沿用旧11/2统计。

### 第8轮当前交接与未完成

- 新Allure `outputs/message-private-20261020-screenshots/allure-report` 成功生成，HTTP本地服务18865；实际15项11 passed、4 failed。13项原检查均有中文测试内容/准备/执行/验证点和PNG；新增mixed准备也有PNG。末条mixed发送失败后截图出现Blocked，未取得PNG，报告已说明。校验所有case均有PNG的断言因此失败，不声称15项全部有图；未更换他人或失效会话来补造现场。
- mixed完整序列当前因频控未完成，原生混合显示步骤未执行；发送结果query参数修复、三轮原失败、找回及限流详见[独立记录](2026-10-20-private-image-send-entry.md)。保留当前21秒节奏候选失败，不标为有效解决频控。
- 本轮已确认新增15条私信、6份图片上传资产按产品保留；首轮混合孤立发送通过原requestId核对并确认未读归零，原异常与后续恢复分开记录。未清空历史。
- 用户随后提供61209清理报告：已转入核对，无额外设备测试。该报告显示dev-api正确、请求响应已有子步骤附件，实际DELETE权限失败；详见[环境核对第2轮](2026-10-19-test-api-environment.md)。发布作者尚未查明，不能推断或删除其他账号笔记。
- 当前未完成：完整混合序列真机显示、末条缺图、实际App输入框/选图发送、其他消息全量。下轮先检查设备归属与有效会话，再确认当前频控规则；不自动重发未知请求，不以离线58 passed替代业务结论。
