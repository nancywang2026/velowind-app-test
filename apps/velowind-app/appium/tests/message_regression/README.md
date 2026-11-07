# 10 月消息功能回归

## 2026-10-20 真实执行入口

账号已配置并完成 A/B/C 登录与身份核对，A 的管理端会话也已核对。新增入口直接调用实际接口，无需手填 `operations`。

| 入口 | 已核实范围 | 本轮结果 |
| --- | --- | --- |
| `live.py --suite groups --images` | 同一新群的邀请、成员、置顶免打扰、改名公告、权限、双向文字图片、分页、清空、移除退出 | 12 passed、1 blocked；成员编辑公告接口能力未开放 |
| `ios_live.py` | C 真机发件界面、A 接收/已读API、三条私信重进与最新定位 | 重进/底部最新定位 passed；已读图标 failed，重进仍为“已发送”；旧历史稳定采样后仍偏移26像素，failed |
| `interactions.py --post-id` | 复用 C 已有笔记，本轮评论 @、回复、点赞收藏和对应通知 | @、回复、点赞通知 passed；收藏生效但通知未出现，failed |
| `publication_live.py` | 复用原笔记发布用例，在原清理前验证审核终态与系统通知 | 原发布步骤在“我的笔记”加载失败，通知未验证；不能把提交成功当发布成功 |
| `payment_mock.read_activity_enrollment` | 本轮报名详情 + 收银台的付款人、金额、支付单绑定及 MAIN 全款阶段 | 离线验证，未执行实际活动支付回调 |

API 通过不等于原生界面通过。群解散后产品保留只读历史，上传图片也保留；私信不清空已有会话，新增消息ID登记为残留。评论只删除本轮评论，取消互动后查询计数恢复为0。

```bash
# 实际群聊API回归：同一fixture复用一个群，最后解散
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.live \
  --accounts .private/message-regression/accounts.json --suite groups --images \
  --output outputs/message-live/groups

# 对已有自有Appium会话执行私信真机断言，不创建或替换会话
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.ios_live \
  --accounts .private/message-regression/accounts.json --session /absolute/owned-session.json \
  --output outputs/message-live/private-native

# 原笔记发布后追加通知；C为手机当前账号，A为管理端审核身份
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression.publication_live \
  --accounts .private/message-regression/accounts.json --session /absolute/owned-session.json \
  --output outputs/message-live/note

# pytest入口：未明确启用时不登录、不写数据、不连接设备
VW_MESSAGE_LIVE_API=1 VW_MESSAGE_ACCOUNTS=/absolute/accounts.json \
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
  apps/velowind-app/appium/tests/message_regression/test_live_messages.py -v
```

`owned-session.json` 包含本轮自有会话的 `server`、`session_id`、`udid`、`bundle_id`。它不包含凭据，也不能用其他任务的会话代替。执行前仍需核对设备占用；只有明确独占设备才允许导航。

评论 pytest 使用 `VW_MESSAGE_EXISTING_POST_ID` 指向当前业务测试的 C 作者笔记；入口再次核对作者、可评论状态。不会另建笔记测通知。

原报名用例现可调用 `run_activity_signup_case(..., notification_observer=EnrollmentObserver(...))`，消息断言位于本次提交后、finally清理前；`ending` 支持本人取消、A管理端取消或审核拒绝。ID通过提交前后差集、创建时间和付款人核对，禁止选择旧报名单。付费分支需要注入实际确认支付及受限mock completion；退款必须查询真实SUCCEEDED才检查退款通知。该报名链尚未实测，不能算已完成的活动消息覆盖。

## 早期绑定式入口（保留）

CSV 中全部 **34 组、59 个参数化分支**已有 Python 流程顺序和断言定义，见
`velowind_appium/message_regression/journeys.py`；但真实业务/UI 操作绑定仍待接入，不能称为全部功能已实现或可直接真机执行。
当前默认配置的绑定审计为 **34 组 blocked**。旧 `message_system` 的 13 个桥接场景保持不变，不计入本次真实覆盖。

已落地的共用代码：

- 直接认证业务 API 客户端；无自动写重试、无重定向，不记录认证响应和请求凭据。
- 通知按操作前 inboxId 基线、通知类型及本轮 bizId 匹配；详情目标再核对，重复事件失败。
- 私信真实接口发送、接收历史窗口/游标、会话未读计数；不拿 `afterMessageId` 同步当作完整历史向前翻页。
- 群创建、详情、成员分页及搜索、关注关系恢复、真实 @ 评论/回复的 API 方法。
- Appium 原生操作、唯一元素选择及最新消息与输入区的几何检查；未核验定位显式阻塞，不填写虚构 `message.*` ID。
- 业务通知钩子：原业务操作只执行一次，随后验证通知，再执行原清理；通知失败也清理。笔记公共发布和活动发布已提供可选 `notification_observer` 接口；真实 observer 配置和报名流程尚待接入，默认不启用消息断言。
- 全流程预检、失败与 cleanup-pending 分开报告；准备结果不明时仍走该 run_id 清理入口。
- 支付回调沿用 [模拟支付工具](../../docs/payment-mock.md)，但尚未接入活动报名适配。

## 功能范围

| CSV 编号 | 流程 |
| --- | --- |
| MSG-001、001-R、032 | 笔记发布/拒绝、活动发布后通知 |
| MSG-002—005、005-RENTAL | 报名、拒绝、本人/领队取消、活动/租车退款通知 |
| MSG-006—009 | 分类、评论赞收藏、关注回关、评论 @ 与回复 |
| MSG-010—016 | 私信文字图片、最新定位、历史、阅读图标、清空、分享、发送故障 |
| MSG-017—029 | 活动群、建群、邀请、成员数、置顶、免打扰、清空、历史、搜索、公告、移除/退出、资料及解散 |
| MSG-030—031 | 私信/入群隐私矩阵候选，须确认10月范围才启用 |

10 月明确不支持的隐藏/恢复、群审批、群公开广场、视频导航、撤回等未加入。原 Fail 功能仍作为回归目标。
故障注入、退款测试渠道、历史可见规则和候选隐私范围分别有能力条件，不能用其他分支通过替代。

## 数据与设备前置

用户已明确沿用 Postman A/B/C。已通过 Postman 正常导出 `0 - dev` 和 `2. 私聊顺序测试环境（请填写）`，两份导出均无有效账号及 base_url 值；没有读取 Postman 私有数据库。临时文件权限为 0600，未放进测试配置或本说明。

执行配置使用 `execution.example.json` 结构，并由 `VW_MESSAGE_REGRESSION_CONFIG` 指向私有文件。支持 `accounts_file` 指向按角色分组的账号 JSON：`accounts.a` / `accounts.b` / `accounts.c` 各包含 `username`、`password`、`user_id`、`name`。其中 `username` 是手机号登录账号，内部映射为 `phone`。相对路径按执行配置文件所在目录解析。当前私有文件为仓库 `.private/message-regression/accounts.json`，已设0600并被Git忽略；已填写值在格式转换时保留。

仍兼容 Postman 环境文件；同名进程环境变量优先于账号文件。`leader` / `admin` 可额外配置，不能拿普通账号假冒审批身份。

- App 实际 API origin 证据、支付单环境、消息业务环境必须一致；Postman 选中 dev 或设置变量不足以证明手机环境。
- 每个 UI 角色暂要求独立、已登录且明确归本轮所有的设备；尚未实现自动切账号。单设备脚本需要后续接入可核验的账号切换操作，不能把同一登录态标成不同角色。
- 驱动创建前检查其他 pytest 进程和目标 Appium server 的 `/sessions`，已占用时阻塞，不结束他人进程。
- 每个设备声明 `udid`、`server_url`、`owned_by_this_run: true`、身份 locator 及证据；UI 必须读出对应账号 ID 才执行场景。
- 同一业务流程复用本次实体和 run_id，不能依赖另一条 pytest 用例的执行顺序。

## 操作绑定与待完成工作

`Program` 只执行真实 `api`、`ui` 和 `assert` 步骤。每个 operation 必须有来源 `source`；locator 必须有现场或 XML 证据 `evidence`。绑定的 `output` 从步骤查询结果提取事实，不能填期望响应。

例如查询会话的可用 API 步骤（不代表完整测试已绑定）：

```json
{
  "source": "Postman 私聊 collection：B查询私聊列表",
  "steps": [{
    "kind":"api", "actor":"b", "method":"GET",
    "path":"/api/v1/mobile/message-center/private-conversations", "save":"response"
  }],
  "output":{"items":"${response.items}"}
}
```

执行顺序固定为 `prepare.<CSV编号>` → 已定义业务/观察操作 → 明确断言 → `cleanup.<CSV编号>`。
清理操作要实际查询剩余实体，返回 `remaining_ids: []` 和实际恢复结果 `restored: true`；不能硬编码空列表代替清理。创建/提交超时后也需按 run_id 查询可能已写入的资源。

仍需实现并验证：各编号具体准备/动作/观察/清理绑定、发布 observer 的实际对象ID与终态查询配置、报名脚本的钩子插入、账号切换或多设备配置、媒体选择和远端可用性、真实图标定位、活动订单支付/退款映射。`coverage-audit.json` 会逐组列出缺项，不能把这部分工作转述为已经完成。

## 验证与执行

```bash
# 无设备：输出每组真实接入缺口
PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m velowind_appium.message_regression \
  --output outputs/message-automation-20261019/coverage-audit.json

# 无设备：离线逻辑验证
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_message_regression.py \
apps/velowind-app/appium/tests/unit-test/test_payment_mock.py -q

# 配置齐备后，明确启用；先单场景验证，再扩大
VW_MESSAGE_REGRESSION=1 VW_MESSAGE_REGRESSION_CONFIG=/absolute/private/execution.json \
VW_APPIUM_AUTO_OPEN_REPORT=0 .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/message_regression -k MSG-010 -v
```

当前连同既有消息、支付、发布公共逻辑合计 89 项离线测试通过，59 个测试入口可收集；默认未启用时实跑59 skipped，未创建驱动。这是早期实现阶段的结果。本轮实际API、真机结果见上节；34组完整业务/UI覆盖仍未完成，不能将新增20个pytest入口当作全部消息功能通过。
