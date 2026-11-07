# 2026-10-19 活动卡片被快照深度截断

## 范围与当前状态

- 用户要求：所有自动化 case 通过；涉及活动详情和可报名活动发现。
- iPhone 17 / App 1.3.0 build 64 / dev-api；最后核实 2026-10-19。
- 当前状态：配置单元首轮通过；80 深度真机无效，已改为现场可读取卡片的 60，完整目标复验待执行。
- 历史索引无相同快照深度记录；旧视频缺 ID 与当前活动截图不能混为同一原因。

## 失败证据

- 运行 `20261019-device-test-full-r1`，目录 `.tmp/appium-ios/runs/20261019-device-test-full-r1/`，无临时 URL。
- 两条报名用例因找不到 signup-capable 活动而被既有 pytest.skip 逻辑跳过，不能计为通过；活动详情用例失败 `Unable to open the first activity detail`。
- 首条报名 XML `allure-results/269117ba-a034-4641-ac86-4a8f9dee2ac1-attachment.xml`、PNG `9bf854bf-2ff1-48de-a57b-4e6963802927-attachment.png`。
- 截图显示多个正常活动；XML 整个活动列表只剩汇总祖先，最后一个含全部活动文字的叶子恰在第 50 层，全树最大深度也是 50。
- 从原 XML 调用 `_activity_card_tap_point_groups` 为 `[]`。因此目前不能把未找到可报名活动判断为后端无数据。

## 第 1 轮：分析、修改与验证

- 已确认：Appium/WDA 快照深度截断，卡片子节点不在返回的页面树中。
- `config.py`：默认 `snapshot_max_depth=80`，通过 `appium:settings[snapshotMaxDepth]` 在会话创建时应用；`VW_IOS_SNAPSHOT_MAX_DEPTH` 可覆盖。README 同步说明。
- 单元命令：`VW_APPIUM_AUTO_OPEN_REPORT=0 PYTHONPATH=apps/velowind-app/appium .venv/bin/python -m pytest apps/velowind-app/appium/tests/unit-test/test_config.py -q`，22 passed，0.06 秒；覆盖默认 80 和显式 100。
- 为继续观察本轮后续用例，2026-10-19 16:11 左右通过当前自有 Appium session 的 settings API 将 snapshotMaxDepth 更新为 80，返回成功；没有创建新会话。当前运行前后快照配置不同，不把整轮作为统一配置最终回归结果。
- 真机活动详情及报名目标仍需在统一新配置下复跑；没有通过跳过、固定点击或替代数据制造通过。
- 本问题涉及只读发现；原两条报名尚未填写或提交订单，未新增报名数据。
- 无失败代码修改尝试。

## 遗留项与交接

- 本轮结束后以默认 60 深度复跑详情与两条报名，确认深层卡片、真实报名资格和订单结果。

## 第 2 轮：80 深度触发 XCTest 错误，收敛至 60

- 首轮 22 配置单元仅验证 capability 传参，不代表 80 深度真机可用。
- 真机设置 80 后，WDA 日志反复 `kAXErrorIllegalArgument getting snapshot`，页面源读取失败；“我的活动点赞列表”在 setup 报 `Home feed did not become ready; page_source=<empty>`（152.83 秒）。截图仍是正常 App 列表，不能解释为网络无活动。
- 该轮 80 候选无效，已回退并将当前自有会话改为 60；GET source 恢复，返回字符串长度 301002。证据 `.tmp/login-fix-investigation/depth60.xml`。
- 现场 60 深度页面树最大深度 60，`_activity_card_tap_point_groups` 识别 6 组，`extract_visible_activity_card_texts` 识别 6 张可见卡片。原 50 深度同页面类型为 0 候选。
- 将最终默认值改为 60；保留 `VW_IOS_SNAPSHOT_MAX_DEPTH` 显式配置能力。80 及更高未证明适用于此设备，不作为推荐运行值。
- 最终 60 配置单元复跑 22 passed，0.07 秒；统一 60 的真机完整目标仍待执行。本轮中途 50→80→60，结果仅用于诊断，不能当作最终统一配置整套通过。
