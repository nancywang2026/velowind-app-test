# 2026-09-18 私聊接收侧 clientMessageId 断言

## 范围与当前状态

- 用户要求修复私聊用例并验证；涉及checks.message、scenario接收断言、HTTP测试夹具。
- 当前状态：脚本修复，真实接收侧局部验证通过；不是整套通过。
- 历史参考：API工程VALIDATION.md只证明离线通过；旧夹具向接收者错误返回了发送者clientMessageId，本次不适用。

## 失败证据

- `.tmp/private-chat-api/reception-verification.json`，首次仅接收侧诊断失败：clientMessageId mismatch。
- 入站历史返回direction=INBOUND、clientMessageId=null；消息ID及正文存在。
- 后端PrivateMessageApplicationService.toView明确仅在currentUserId等于senderUserId时返回clientMessageId，否则null。

## 第1轮：修改与验证

- checks.message增加recipient_view：接收视角要求INBOUND及clientMessageId为空；发送响应仍严格核对clientMessageId。消息ID、正文、双方身份、会话、卡片业务ID均保留断言。
- 本地HTTP夹具按真实后端隔离发送者clientMessageId，新增防止错误接收人的负例。
- `pnpm api:private-chat:unit`：60 passed、1 deselected。
- 只读实际复核：`.tmp/private-chat-api/reception-verification-run2.json` 及对应allure-results：passed；B收到3文本+1笔记卡片，C收到5文本。
- 使用已发消息ID复核，不重新发送；首次失败报告保留。

## 遗留项与交接

- 活动卡片发送仍因provider unavailable阻断，见活动卡片记录；未验证其接收。
- 真机：未执行。
- 清理：未删除任何消息；只读复核不改变已读状态。
