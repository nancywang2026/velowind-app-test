# 2026-10-20 私信图片发送结果查询缺少sendEntry

## 范围与当前状态

- 用户重点：文字图片发送、顺序及显示正确。历史参考：[私聊发送节奏](2026-09-18-api-private-chat-unread-baseline.md)、[消息脚本与报告](2026-10-19-message-regression.md)。当前：已修复私信发送结果查询参数，真实图片SENT与完整混合序列执行分开统计。

## 第1轮：真实失败与修复

- `outputs/message-private-20261020-mixed-first-attempt/live-results.json`：上传2张成功，首条文字成功，图片POST已成功但GET发送结果HTTP400 / 10010001 / common.bad_request；未自动重发图片。
- 当前dev OpenAPI明确私信GET必须有query `sendEntry=CONVERSATION|LEGACY`；原 `business.Messages.send` 群和私信共用轮询，遗漏私信必填参数。修改：group维持原路径，private查询增加 `params={'sendEntry':'CONVERSATION'}`，原POST的requestId保持一致。
- 使用原requestId和正确参数只查询，找回原图SENT，核对assetId及C接收方向；2条本轮消息确认未读0。原case失败和原cleanup异常保留，追加 `unread_reconciliation.status=confirmed-zero`，没有把失败改写为passed，没有重新发送原请求。
- 离线新增私信轮询参数、原请求ID和只发送一次断言；相关58 passed，0.15秒，`.tmp/appium-ios/runs/20261020-113831-96611/timing/`。

## 第2轮：频控失败保留

- `outputs/message-private-20261020-mixed-rate-limit-attempt/live-results.json`：正确参数使首张图片SENT成功；发送3条后，第4条HTTP400 / 17000028 / message.private.rate_limited。3条已确认消息保留，未读实际归0。不是图片上传失败。
- 阅读历史发送节奏记录后，候选增加首条前61秒窗口等待、各条21秒间隔；依据历史记录，当前仍须实测。
- 候选结果 `outputs/message-private-20261020-screenshots/mixed/live-results.json`：准备passed，发送子检查在126.214秒仍被rate_limited拒绝，仅3条已确认；21秒间隔当前条件下不足。未自动重试写入，未放宽断言。
- 图片已可由真实接口发送并恢复SENT；完整5条混合序列、双方完整字节对照和原生混合顺序/像素显示尚未通过真机验证，后续步骤未执行。不得把新增离线测试当作这些业务检查通过。
- 窗口限流规则是否已改变、是否存在同期相同发送账号流量未确认。用户随后提供另一份同期发布报告；没有因此推断它产生了私信或导致频控。
- 下一步需先读取当前频控规则或取得明确的限流业务参数，再确定发送节奏；保留全部失败，不关闭后端限制、不凭空增加通过结果。
