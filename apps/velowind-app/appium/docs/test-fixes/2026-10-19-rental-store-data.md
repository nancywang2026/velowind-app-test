# 2026-10-19 租车门店名称与实际数据不匹配

## 范围与当前状态

- 用户要求：所有自动化 case 通过；用例 `test_user_can_create_rental_order_and_leave_payment_unfinished`。
- iPhone 17 / App 1.3.0 build 64 / dev-api；最后核实 2026-10-19；26 相关单元通过，真机完整复验待执行。
- 历史参考：[租车自动取消](2026-09-30-rental-order-cleanup.md)，本轮尚未下单，不套用其清理成功结论。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- `choose-first-store` 失败：`Unable to select the first rental service store`。
- 原 XML `allure-results/cf93396c-3088-48c8-83bf-6393af6f5a0e-attachment.xml`；PNG `0e01ae1a-072b-40dc-a8d2-db2901c0ec9e-attachment.png`，实际仍在租车页未选择门店。
- 整套结束后确认无 pytest，再独立打开实际门店选项；`.tmp/login-fix-investigation/rental-store/options.{xml,png}` 明确只显示“上海徐汇店”，并非旧代码固定文本“虹桥店”。调查会话已 quit，未创建订单。

## 第 1 轮：修改与验证

- `rental_store.py`：对实际可见门店名称增加选择路径，忽略占位标题及隐藏祖先中的名称；优先保留既有定位 ID / 名称，使用精确选项文本点击，不新增固定坐标。
- 保留选中结果及后续选车/订单断言；不跳过门店或租车数据。
- 新增实际名称、占位标题和隐藏候选单元覆盖。
- 命令：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_rental_helpers.py -q`，26 passed，0.06 秒；既有 LibreSSL warning。
- 原运行实际清理：未下单，无新增租车订单；完整真机修复复验待第二轮整套。
- 无失败修改尝试。

## 遗留项与交接

- 第二轮完成后核对订单断言与本轮订单自动取消结果，二者分别记录。
