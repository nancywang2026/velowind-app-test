# 2026-10-19 按 Postman 实现测试支付模拟回调

## 范围与当前状态

- 用户要求：参考 Postman collection 实现模拟支付成功；从本轮测试订单获取所需信息，先确认测试环境。
- 模块：新增 `velowind_appium/payment_mock.py` 及独立离线测试；未修改已有真机用例、订单清理、登录、环境配置。
- 当前状态：26 项离线测试通过；实际业务环境/本轮订单及在线回调未验证，不是整套通过。
- 历史参考：[测试环境 API 映射](2026-10-19-test-api-environment.md)。其中明确环境配置不等于安装包实际环境，继续适用。
- 最后核实：2026-10-19；未连接新 Appium 会话。

## 需求证据与初始限制

- Postman 选中 `🔴 【本地MOCK】用户 A 模拟ALIPAY支付成功回调`，环境显示 `0 - dev`；UI Body 核实为 urlencoded 的 `paymentOrderId` 与 `trade_status=TRADE_SUCCESS`。
- 已读取用户目录对应租车支付 collection：主支付单可能尚未创建；正常支付准备必须取得业务订单绑定的 ID，不能照抄旧环境变量。
- collection 明确后端须启用 `payment.sdk.enabled` / `payment.sdk.mock.enabled`；本轮未改变服务开关。
- Postman 首次取应用状态因 ScreenCaptureKit -3811 失败，重试应用绑定后 AX 成功；取截图因 -3812 失败。改读正常导出的 collection 文件，不猜脚本内容、不从 App 私有数据库提取配置。

## 第 1 轮：实现与失败

### 修改

- 封装表单回调、认证支付单查询及租车订单查询；核对本轮 ID、归属、金额、可支付状态和绑定。
- 仅精确允许 `https://dev-api.velowind.com`，要求调用者提供匹配的实际 App origin 和环境证据；不以 Postman 环境名自动确认手机环境。
- 发送前校验 DIRECT/THIRD_PARTY/ALIPAY 路由；订单无绑定支付单时报前置错误，不自动新建或调用 `/pay`。
- 回调仅一次，响应结果不明则查询；支付及业务订单支付状态同时成功才返回，业务生命周期与通知仍需原用例验证。

### 失败与原因

- 首次 pytest 收集失败：项目 Python 3.9 不支持在运行时直接求值 `str | None`，`TypeError: unsupported operand type(s) for |`。
- 时间报告：`.tmp/appium-ios/runs/20261019-162613-32877/timing/`。
- 加入 `from __future__ import annotations` 修复，保留本次失败记录。

## 第 2 轮：验证

```bash
VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest \
apps/velowind-app/appium/tests/unit-test/test_payment_mock.py -q -o addopts=''
```

- 26 passed，0.06 秒；既有 LibreSSL warning。
- 时间报告：`.tmp/appium-ios/runs/20261019-162622-32909/timing/`。
- 覆盖错误环境/对象/归属/金额/支付状态/路由时不回调，已成功不重放，丢响应查询成功，无业务同步不误判成功，同一client不重复回调，表单编码/noauth及禁止重定向。
- 接口网络调用均由离线 transport 替身拦截；没有任何真实回调或订单改动。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 |
| --- | --- | --- |
| 正常导出 collection + Postman AX Body | 读取当前回调契约 | 已确认两项表单字段；未把正文JSON或猜测签名作为回调 |
| 业务订单内部ID查询绑定支付单 | 原用例已记录订单与归属 | 租车 reader 已实现；报名须独立确认字段映射 |
| 仅看 HTTP 成功 | 回调渠道ACK | 不足以判支付成功，必须复查支付与业务状态 |

## 遗留项与交接

- 使用方式见 [模拟回调说明](../payment-mock.md)。无直接 CLI，避免误用旧订单执行。
- 实际环境核实、当前测试订单查询、在线回调、App最终状态、报名/退款/通知均未验证。
- 活动报名 reader 未实现：当前只确认组织者详情引用，不将其冒充报名人订单查询契约。
- 同一client防重已覆盖；跨进程执行账本尚未提供，再次运行需先查前次记录和实际状态。
- 16:27 左右检查发现另一 pytest 真机 suite PID 32435 正在运行；未替换会话、结束他人任务或点击手机支付。
- 清理状态：本轮没有线上资源创建/修改，清理不涉及；不继承其他测试的清理完成结论。
