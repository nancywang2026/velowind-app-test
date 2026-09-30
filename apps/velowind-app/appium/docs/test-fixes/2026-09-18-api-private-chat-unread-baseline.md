# 2026-09-18 私聊 API 未读基线阻断

## 范围与当前状态

- 用户要求：修复失败私信用例并验证，报告使用 Allure。
- 模块：`apps/velowind-app/api-tests`，独立 API 脚本；不修改 Appium 流程。
- 当前状态：基线和发送节奏已修复、真实局部通过；整套因活动provider不可用阻断。
- 历史参考：API工程 VALIDATION.md；此前已确认基线26，原实现要求人工已读，重复运行仍阻断。

## 失败证据

- URL： http://127.0.0.1:64200/#suites/04a7d338a2a3d97e6bda490162a0378f/b514263a53dc538c/
- 原报告用例ID：b514263a53dc538c；本地证据 `.tmp/private-chat-api/failing-allure-case.json`。
- 登录A/B/C、A关注B成功；03 B未读基线失败，`Unread baseline mismatch`。
- 附件确认 baseline_unread_b=26，而配置预期0；该轮尚未发送测试消息。

## 第1轮：分析、修改与验证

### 分析

已确认是测试前置数据不可复用，不是登录或消息发送接口报错。不能将预期总数放宽为29来宣称“总未读3条”通过。

### 修改

新增独立 Conversations.mark_read；通过 preparation.mark_b_history_read 开关，仅以B身份对A的会话调用已读接口。校验返回会话ID、已读数量、剩余未读0，再查列表确认基线。当前local和example启用；缺省仍为false，旧配置保持严格前置检查。已有历史不删除，其他会话不处理，开始发消息之后不再调用已读。

断言仍保留基线0、最终总数3、增量3；准备前数量和实际已读数量进入Allure脱敏附件。

### 验证

待追加单元和实际API结果。已检查进程，无其他私聊API/pytest执行进程；存在Appium服务，不操作或结束它们。此任务无需真机。

## 遗留项与交接

- 真机：未执行，不在本次API验证范围。
- 清理：历史消息不删除；准备会改变B与A会话历史已读状态。后续真实运行产生的消息和会话修改不自动回滚，另行记录。

## 第1轮实际结果与第2轮限流修复

- 离线57 passed，1项真实测试未选中。
- 实际报告 `.tmp/private-chat-api/baseline-fix-run1.json` 与 `baseline-fix-run1/allure-results`：历史未读26，标读26后基线0；A→B三条成功，总数3；A→C前两条成功，第3条HTTP400，业务码17000028，`message.private.rate_limited`，规则sender_minute。
- 该轮实际新增5条文本；未清理，不算整套通过。
- 核对后端application.yml默认sender-per-minute=5、pair-per-minute=3。因此新增execution.send_interval_seconds=21，仅限制私信发送（包含分享），查询不额外等待。不自动重试写入，也不修改服务端限流。
- 后续将按发送间隔完整复测，保留本轮失败。

## 第2轮实际结果

- 离线58 passed、1项真实测试未选中。
- `.tmp/private-chat-api/baseline-fix-run2.json`：登录通过，关注请求Transport/JSON failure，无HTTP响应，未进入发送阶段；关注结果可能未知，不自动重试该请求。
- 第1轮已确认该方向关注存在，关注API重复关注为幂等成功（控制器契约）。继续一次新的完整运行，保留第二轮网络失败，不算通过。

## 第3轮实际结果与最终状态

- `.tmp/private-chat-api/baseline-fix-run3.json`：准备前未读3，标读3后基线0，发送3条后总数3；C五条文本全部成功，置顶、隐藏、笔记分享通过。
- 21秒发送间隔有效，本轮未触发频控；第10步ACTIVITY卡片因后端17000025阻断（独立记录），新增9条消息，未清理。
- 接收侧另发现clientMessageId视角断言错误，修复后只读验证B四条、C五条通过，详见接收侧记录。
- 最终离线60 passed、1 deselected。基线和发送节奏问题已修复并实测通过；整套仍未通过，保留所有失败轮次。
- 原始失败轮次、3次复测与独立诊断已合入默认 `.tmp/private-chat-api/allure-results`，HTML目录 `.tmp/private-chat-api/allure-report`。
- 当前无本任务运行中的API进程；不涉及真机会话。
