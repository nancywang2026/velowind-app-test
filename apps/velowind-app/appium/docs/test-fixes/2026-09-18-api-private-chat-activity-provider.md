# 2026-09-18 活动卡片provider不可用

## 范围与当前状态

- 当前状态：真实后端/活动数据阻断，未通过；没有跳过断言或改为假数据。
- 涉及：私聊ACTIVITY分享；未修改后端服务或数据库。
- 用户要求：修复私聊接口测试并验证。

## 失败证据

- `.tmp/private-chat-api/baseline-fix-run3.json`，步骤10：HTTP400，code=17000025，messageKey=message.private.context_provider_unavailable，contextType=ACTIVITY。
- 请求不含bizType，符合ACTIVITY合同；当前bizId=route-992391bc5408456e97b9e5d144c42701。
- traceId=67311fa0-6a2a-48db-a797-569b42f15245。
- 独立诊断另一公开活动route-9cfaef52ad474a6b917cd0b9ea600f4f，同样400/17000025，traceId=c5fbc2d1-5d9a-47de-b239-9223af6abce0。
- 报告 `.tmp/private-chat-api/activity-diagnostic.json` 和对应allure-results；诊断使用不同Allure测试身份，不冒充整套结果。

## 第1轮：核实

- 公开GET /api/v1/mobile/activity/routes与/routes/{routeId}能查到原活动，详情含标题、描述、ownerUserId、profile.imageUrls，列表含coverImageUrl。
- 已纠正分析中的错误推断：不能根据route-前缀认定ID填错。后端buildActivityContextCard确实通过routeRepository.findByRouteId解析ACTIVITY的bizId。本地activity_id保持原值，没有随意替换。
- 源码发现可能的封面兼容问题：ActivityInternalApiImpl.buildActivityContextCard从profileJson读取coverUrl/coverImageUrl/imageUrl；原详情仅暴露imageUrls数组。适配器要求非空cover。此为源码线索，不是已核实部署实例内部快照，需服务日志确认。
- 独立尝试另一公开活动也失败，未产生该诊断的活动消息。未改后端安全/频控配置，未删除数据。
- HTTP错误摘要增强为包含安全业务码及messageKey，便于在Allure顶层看到原因。

## 遗留项与交接

- 需后端按上述traceId核查activity provider快照字段和部署版本；修复后再运行pnpm api:private-chat。
- 目前不能声称完整用例通过；C活动卡片接收及分享后的最终列表未验证。
- 真机未执行；已成功写入的文本、笔记分享及关注/置顶/隐藏状态未回滚。

## 第2轮：用户报告 bcaee9add7779a70 复核（2026-09-18 17:37）

- 原报告：http://127.0.0.1:62671/#suites/04a7d338a2a3d97e6bda490162a0378f/bcaee9add7779a70/ 。步骤01–09通过，步骤10返回400/17000025；步骤11及以后未执行。
- 原请求clientMessageId及X-Request-Id均为有效UUID：2972eef5-9ad3-451f-8d42-f812daa35988；已排除此前Postman字面量$guid问题。原traceId=1c0b3e28-df12-484a-b475-558eab16d96f。
- 使用现有load_config/login/HttpClient/Messages/Sharing模块，只登录A/C并重新发送一次相同活动分享，未重跑前9步。仍返回400/17000025，request_id=b595e16b-b450-4ed9-bc1e-4ba03e0abdfc，traceId=c3ab10b9-79f9-4716-9989-f361f92e3ac0。
- 报告：`.tmp/private-chat-api/activity-recheck-20260918/journal.json`、`allure-results/`、`allure-report/`，已自动打开。使用独立测试身份，不能视为整套结果。
- 当前源码仍从profile的coverUrl/coverImageUrl/imageUrl取封面，适配器要求coverUrl非空；封面兼容仍是推测，未读取部署服务日志确认。
- 测试请求符合ACTIVITY合同，因此未修改请求类型、资源ID或放宽断言。未修改/部署后端，未执行单元测试（本轮无测试代码变更）。
- 清理：本轮无成功发送响应，未执行清理；历史消息未回滚。真机未验证。当前仍待后端按traceId核实provider失败原因并修复，之后重跑完整用例。
