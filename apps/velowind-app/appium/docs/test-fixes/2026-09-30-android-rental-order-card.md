# 2026-09-30 Android 租车订单卡片误读

## 范围与当前状态

- 用户要求：修复所给 Allure 失败用例并在真机验证。
- 用例：`tests/rental/test_rental_order.py::test_user_can_create_rental_order_and_leave_payment_unfinished`。
- 平台：Android 真机 `YHK7EERSGAPZX87X`，App `com.velowind.rider`；本用例不包含订单清理。
- 当前状态：25 单元通过，目标 Android 真机用例通过；本轮订单未清理。
- 最后核实时间：2026-09-30。
- 历史参考：索引中无同一租车订单误读记录；iOS 效率记录提到过不同的提交失败，不能用于本次结论。

## 失败证据

- 报告：`.tmp/appium-android/runs/20260930-150651-97811/allure-results/`；原始 URL：`http://127.0.0.1:63381/#suites/efb7a3a9d019b3e7f0e667805bb5195f/716baba01b541e46/`。
- 失败步骤：`12-read-my-rental-unfinished-order`，`Latest rental order summary is incomplete`，解析到旧订单 `RO1790740144430B7F6A5`，缺少剩余支付时间。
- 截图：`7a5b217b-b252-4494-a39b-663aea04260e-attachment.png`，XML：`573999bd-2db1-4ab1-b205-4ed3316b6ec1-attachment.xml`，均在上述报告目录。
- 现场：支付中心截图中的新订单为 `RO17907532487191726B2`；失败截图前台为旧订单详情且显示“已取消”。XML 同时含后台“我的租车”列表，其第一张卡片为新订单，显示“待支付”“支付未完成，可重新发起支付。”“去支付”及三项日期；该 Android 卡片未显示“剩余支付时间”。
- 预期：验证本轮新建订单的待支付状态与重付入口。实际：解析器跨两个页面取值，把旧详情订单号和新卡片状态混合。

## 第 1 轮：分析、修改与验证

### 分析

- 已确认：解析器读取整个 XML 的可见文本，未按本轮订单号隔离卡片；Android 卡片无倒计时字段，原断言却要求该字段。
- 仍待确认：支付对话框关闭后为何前台回到旧订单详情；本轮先用订单号约束解析与断言，真机复测观察。

### 修改

- `modules/rental_orders.py`：支持按提交订单号提取 Android 单张订单卡片；Android 完整性检查允许该卡片没有倒计时，仍要求订单号、三项时间、待支付和重付入口。
- `tests/rental/test_rental_order.py`：支付中心记录本轮订单号，最终只核对同一订单。
- `tests/unit-test/test_rental_helpers.py`：加入旧详情与新卡片共存的回归用例。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_rental_helpers.py -q
```

- 单元：23 passed。原始 XML 离线解析得到新订单完整的待支付卡片。
- 真机：待执行。
- 清理：用例未定义清理，待支付订单可能保留；与断言通过情况分开记录。
- 本轮结论：离线证据支持修复，真机结果待补。

## 可复用方法与无效尝试

| 方法 | 适用条件 | 结果 / 不适用原因 |
| --- | --- | --- |
| 从整页 XML 读取第一个订单号 | 多页面同时存在 | 无效；先遇到旧详情 |
| 强制 Android 卡片含剩余支付时间 | 当前真机列表卡片 | 无效；截图和 XML 均未显示该字段 |

## 遗留项与交接

- 已完成：失败证据复核、代码与回归用例修改、单元验证。
- 未完成：真机复测；若前台仍落在旧详情，需核查导航与页面可见性。
- 下一步：确认无其他 pytest 流程占用该真机后，单独运行目标用例，记录报告及订单状态。
- 设备：检查时未发现运行中的 pytest；常驻 Appium 服务在 4725 端口，未结束或替换。

## 第 2 轮：首轮真机通过但前台仍为旧详情

### 新证据与分析

- 命令：`VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/rental/test_rental_order.py::test_user_can_create_rental_order_and_leave_payment_unfinished -q --alluredir=.tmp/appium-android/runs/20260930-rental-order-fix/allure-results`
- 结果：`1 passed`，93.72 秒。报告目录：`.tmp/appium-android/runs/20260930-rental-order-fix/allure-results/`。
- 但 `13-read-my-rental-unfinished-order` 截图 `2adfbd62-6c1d-48db-a699-cd1c22aa8145-attachment.png` 仍是旧订单详情 `RO17907532487191726B2`；支付中心新订单为 `RO1790754402417DFB575`。新订单可从后台列表 XML 解析，不等于在前台完成查看。不能将本次 `passed` 当成页面导航验证完成。
- 已确认：`wait_for_my_rental_page` 被后台列表内容满足，未保证前台为该列表。

### 修改

- `modules/rental_payment_center.py`：Android 关闭支付弹窗后，如 XML 中“订单详情”在“我的租车”前面，执行一次返回并再次等待“我的租车”。
- `tests/unit-test/test_rental_helpers.py`：补充该导航分支的回归用例。

### 验证

- 单元与真机待再次执行。
- 清理：首轮未执行清理，待支付订单保留；第二轮同样需要单独观察。

## 第 3 轮：复测被车辆库存阻断

- 命令：`VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/rental/test_rental_order.py::test_user_can_create_rental_order_and_leave_payment_unfinished -q --alluredir=.tmp/appium-android/runs/20260930-rental-order-fix-r2/allure-results`。
- 结果：`1 failed`，113.09 秒；报告目录：`.tmp/appium-android/runs/20260930-rental-order-fix-r2/allure-results/`。第 7 步找不到可预定车辆，尚未到新改的支付后导航。
- 失败截图：`89a0946c-e652-4792-9a2e-a91599e02785-attachment.png`；XML：`f5b2fe45-a3c2-4e7d-af95-5cf218934869-attachment.xml`。当前虹桥店两张车辆卡均显示“不可预定”。是否由此前待支付订单占用库存仍是推测，尚未证实。
- 单元命令：`PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_rental_helpers.py -q`，24 passed。
- 结论：导航修复的整条真机流程未验证；此次失败不同于原始解析失败。清理：没有执行，前几轮创建的待支付订单仍可能存在。

## 第 4 轮：用户取消订单后真机完整通过

### 分析与修改

- 用户告知已取消订单；此后同一取还车日期重新出现可预定车辆。此前库存阻断与待支付订单占用的因果关系未单独验证。
- `modules/rental_orders.py` 额外检查 Android XML 的前台顺序：若“订单详情”在“我的租车”前，即使后台列表卡片完整也不返回成功，避免第 2 轮误判。
- `tests/unit-test/test_rental_helpers.py` 增加该前台判断测试。无其他生产代码修改。

### 验证

```bash
PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_rental_helpers.py -q
VW_APPIUM_PLATFORM=android VW_ANDROID_TARGET=physical VW_APPIUM_SERVER_URL=http://127.0.0.1:4725 PYTHONPATH=apps/velowind-app/appium ./.venv/bin/python -m pytest apps/velowind-app/appium/tests/rental/test_rental_order.py::test_user_can_create_rental_order_and_leave_payment_unfinished -q --alluredir=.tmp/appium-android/runs/20260930-rental-order-fix-r3/allure-results
```

- 单元：25 passed。
- 真机：目标用例 `1 passed`，101.30 秒；报告目录 `.tmp/appium-android/runs/20260930-rental-order-fix-r3/allure-results/`。第 13 步截图 `0569d8d9-0437-4f9f-875d-72ed34ff15e4-attachment.png` 前台为“我的租车”，首张卡片显示本轮新订单 `RO1790755474818E2A62D`、“待支付”、“支付未完成，可重新发起支付。”和“去支付”。三项时间可见；本轮支付中心订单号与首张卡片一致。
- 清理：本用例不包含取消步骤；本轮新订单仍显示“待支付”，未清理。用户此前取消的订单在截图中显示“已取消”，与本轮结果分开。
- 本轮结论：目标 Android 真机用例通过，最终前台页面已人工核对；此前第 2 轮的误判和第 3 轮的库存失败保留，不计作本轮通过。

## 遗留项与交接（最终）

- 已完成：订单卡片按本轮订单号解析、Android 不要求列表未展示的倒计时、前台导航与防误判、25 单元和目标真机验证。
- 未完成：本轮待支付订单 `RO1790755474818E2A62D` 未取消；整套 Android 测试未复跑。
- 下一步：若需要清理测试数据，取消该待支付订单；整套回归需另行执行。
- 设备：复测前未发现其他运行中的真机 pytest；常驻 Appium 服务沿用 4725 端口，未结束他人进程。

## 后续：自动取消订单

用户进一步要求下单验证后取消订单。该项独立记录于[租车自动取消](2026-09-30-rental-order-cleanup.md)：32 单元通过，完整 Android 目标用例 1 passed，自动取消已真机验证。上述历史通过时未清理的结论保留；订单 `RO1790755474818E2A62D` 后续现场已显示“已取消”。
